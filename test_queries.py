from datetime import datetime
from pathlib import Path
from tool_server.main import uni_agent
# Тестирование агента

test_queries = [
    "Хочу учиться в тёплой стране",
    "Какие университеты есть в Европе?",
    "Посоветуй вуз в Германии",
    "Куда поехать учиться, если бюджет небольшой?",
    "Хочу в Азию, расскажи варианты",
    "Расскажи про университеты в Италии и сколько это в тенге",
    "Где учиться в англоязычной стране?",
]


results = []
for q in test_queries:
    print(f"\n{'='*60}\nQuery: {q}\n{'='*60}")
    try:
        result = uni_agent.invoke({
            "messages": [{"role": "user", "content": q}]
        })
        final_answer = result["messages"][-1].content
        print(f"\n{'='*60}\nAnswer: {final_answer}\n{'='*60}")
        
        tool_calls = [
            msg for msg in result["messages"] 
            if hasattr(msg, "tool_calls") and msg.tool_calls
        ]
        
        results.append({
            "query": q,
            "answer": final_answer,
            "num_tool_calls": sum(len(m.tool_calls) for m in tool_calls),
            "tools_used": [tc["name"] for m in tool_calls for tc in m.tool_calls],
        })
    except Exception as e:
        results.append({"query": q, "error": str(e)})


# === Запись в файл ===
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_file = output_dir / f"agent_run_{timestamp}.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"Agent test run — {timestamp}\n")
    f.write("=" * 70 + "\n\n")
    
    for i, res in enumerate(results, 1):
        f.write(f"{'='*70}\n")
        f.write(f"Query {i}: {res['query']}\n")
        f.write(f"{'='*70}\n")
        
        if "error" in res:
            f.write(f"ERROR: {res['error']}\n\n")
            continue
        
        f.write(f"Tools used ({res['num_tool_calls']}): {res['tools_used']}\n\n")
        f.write(f"Answer:\n{res['answer']}\n\n")
    
    f.write("\n" + "=" * 70 + "\n")
    f.write("SUMMARY\n")
    f.write("=" * 70 + "\n")
    for i, res in enumerate(results, 1):
        if "error" in res:
            f.write(f"Query {i}: ERROR — {res['error']}\n")
        else:
            f.write(f"Query {i}: {res['num_tool_calls']} tool calls — {res['tools_used']}\n")

print(f"\nResults saved to: {output_file}")