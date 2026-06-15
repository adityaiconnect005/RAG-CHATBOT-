@echo off
cd /d "d:\Nextleap\RAG_CHATBOT"
echo --- Starting Daily Ingestion at %date% %time% --- >> ingest_run.log
python test_pipeline.py >> ingest_run.log 2>&1
echo --- Completed Daily Ingestion at %date% %time% --- >> ingest_run.log
