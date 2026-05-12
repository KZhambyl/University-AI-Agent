# start.ps1 - запуск проекта

Write-Host "Starting University Agent..." -ForegroundColor Cyan

docker-compose up -d

Start-Sleep -Seconds 10

Write-Host "Copying pipeline filter..." -ForegroundColor Cyan
docker exec lesson50-pipelines cp /app/pipelines/imported/langfuse_filter_pipeline.py /app/pipelines/langfuse_filter_pipeline.py

Write-Host "Restarting pipelines..." -ForegroundColor Cyan
docker-compose restart pipelines

Start-Sleep -Seconds 15

Write-Host ""
Write-Host "Container status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "Done! Open in browser:" -ForegroundColor Green
Write-Host "  OpenWebUI: http://localhost:3010" -ForegroundColor Yellow
Write-Host "  Langfuse:  http://localhost:3001" -ForegroundColor Yellow

# Выключение: docker-compose down 