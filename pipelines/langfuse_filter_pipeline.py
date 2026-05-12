"""
title: Langfuse Filter
author: DataGroup
date: 2026
version: 1.0.0
license: MIT
description: A pipelines filter that traces all OpenWebUI chat completions to Langfuse.
requirements: langfuse==2.60.5
"""

# =============================================================================
# Langfuse Filter Pipeline (на Pipelines server, port 9099)
# =============================================================================
# Это НЕ функция OpenWebUI (как наши Pipe/Filter/Action).
# Это пайплайн для отдельного Pipelines server, который вешается на OpenWebUI
# как "OpenAI provider" и работает как middleware над всеми чатами.
#
# Почему это отдельный сервис:
#   - Pipelines server -- это OpenAI-compatible OpenAPI endpoint, который
#     может проксировать любые запросы и применять к ним фильтры.
#   - Через него Langfuse видит АБСОЛЮТНО ВСЕ chat completions, не только
#     наших Pipe-моделей, но и любых OpenAI/Ollama моделей в OpenWebUI.
#   - Это production-grade observability layer.
#
# Что делает этот фильтр:
#   inlet  -- открывает новый Trace в Langfuse при каждом запросе пользователя.
#   outlet -- закрывает Trace и записывает model output, latency, token usage.
#
# Каждый chat в OpenWebUI становится отдельным Trace в Langfuse, со всеми
# Generations внутри -- там видны все LLM-вызовы, стоимость, latency, prompts.
# =============================================================================

import os
import time
from typing import Optional, List, Generator, Iterator
from pydantic import BaseModel

from langfuse import Langfuse


class Pipeline:
    class Valves(BaseModel):
        # pipelines:* фильтр применяется ко всем моделям по умолчанию.
        # Можно сузить, например ["openai/*"], чтобы только OpenAI логировать.
        pipelines: List[str] = ["*"]
        # priority: меньше = выполняется раньше (если несколько фильтров).
        priority: int = 0

        # Langfuse credentials. Получаются после первого логина в Langfuse UI:
        #   Project Settings → API Keys → Create new API keys
        secret_key: str = ""
        public_key: str = ""
        host: str = "http://langfuse:3000"

        # debug: подробный stdout-лог в pipelines контейнере.
        debug: bool = False

    def __init__(self):
        self.type = "filter"
        self.name = "Langfuse Filter"

        # Подгружаем дефолтные значения из env (так удобно в docker-compose).
        self.valves = self.Valves(
            **{
                "pipelines": ["*"],
                "secret_key": os.getenv("LANGFUSE_SECRET_KEY", ""),
                "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                "host": os.getenv("LANGFUSE_HOST", "http://langfuse:3000"),
                "debug": False,
            }
        )

        self.langfuse: Optional[Langfuse] = None
        # Кэш текущих trace по chat_id. Один chat = один trace,
        # каждое сообщение в нём = одна generation внутри trace.
        self.chat_traces: dict = {}
        self.start_times: dict = {}

    async def on_startup(self):
        # Вызывается один раз при старте Pipelines server.
        if self.valves.public_key and self.valves.secret_key:
            try:
                self.langfuse = Langfuse(
                    public_key=self.valves.public_key,
                    secret_key=self.valves.secret_key,
                    host=self.valves.host,
                )
                # Проверяем что ключи рабочие
                self.langfuse.auth_check()
                print(f"[langfuse_filter] connected to {self.valves.host}")
            except Exception as e:
                print(f"[langfuse_filter] init failed: {type(e).__name__}: {e}")
                self.langfuse = None
        else:
            print("[langfuse_filter] no API keys set, filter is dormant")

    async def on_shutdown(self):
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception as e:
                print(f"[langfuse_filter] flush failed: {e}")

    async def on_valves_updated(self):
        # Если админ поменял ключи в UI — переподключаемся.
        await self.on_shutdown()
        await self.on_startup()

    # -------------------------------------------------------------------------
    # inlet -- ДО отправки в LLM. Открываем trace + generation.
    # -------------------------------------------------------------------------
    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        if not self.langfuse:
            return body

        chat_id = body.get("chat_id") or body.get("metadata", {}).get("chat_id") or "unknown"
        model = body.get("model", "unknown")
        messages = body.get("messages", [])

        try:
            # Создаём (или находим) trace для этого chat_id.
            if chat_id not in self.chat_traces:
                trace = self.langfuse.trace(
                    name=f"chat:{chat_id[:8]}",
                    user_id=(user or {}).get("id"),
                    session_id=chat_id,
                    metadata={
                        "chat_id": chat_id,
                        "user_name": (user or {}).get("name"),
                        "user_email": (user or {}).get("email"),
                    },
                )
                self.chat_traces[chat_id] = trace
            trace = self.chat_traces[chat_id]

            # Внутри trace — отдельная generation для текущего сообщения.
            generation = trace.generation(
                name=f"completion:{model}",
                model=model,
                input=messages,
                metadata={"model": model},
            )
            # Сохраним generation, чтобы закрыть на outlet.
            body.setdefault("metadata", {})["_langfuse_generation_id"] = generation.id
            self.start_times[generation.id] = time.time()

            if self.valves.debug:
                print(f"[langfuse_filter] inlet trace={trace.id} gen={generation.id} model={model}")
        except Exception as e:
            if self.valves.debug:
                print(f"[langfuse_filter] inlet error: {type(e).__name__}: {e}")

        return body

    # -------------------------------------------------------------------------
    # outlet -- ПОСЛЕ ответа модели. Закрываем generation с output.
    # -------------------------------------------------------------------------
    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        if not self.langfuse:
            return body

        gen_id = (body.get("metadata") or {}).get("_langfuse_generation_id")
        if not gen_id:
            return body

        try:
            messages = body.get("messages", [])
            last_assistant = next(
                (m for m in reversed(messages) if m.get("role") == "assistant"), None
            )
            output_text = last_assistant.get("content", "") if last_assistant else ""

            duration = time.time() - self.start_times.pop(gen_id, time.time())

            # Закрываем generation. Langfuse SDK сам считает usage если он в body.
            usage = body.get("usage") or {}

            self.langfuse.generation(
                id=gen_id,
            ).update(
                output=output_text,
                end_time=None,  # Langfuse автоматически выставит "now"
                usage=usage if usage else None,
                metadata={"duration_seconds": round(duration, 3)},
            )

            if self.valves.debug:
                print(f"[langfuse_filter] outlet gen={gen_id} duration={duration:.2f}s")
        except Exception as e:
            if self.valves.debug:
                print(f"[langfuse_filter] outlet error: {type(e).__name__}: {e}")

        return body
