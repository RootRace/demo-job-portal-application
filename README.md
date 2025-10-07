Install requirements
-----------------------
flask python-dotenv pymupdf python-docx spacy
python -m spacy download en_core_web_sm --> AI model for resume parsing
--> en_core_web_trf       (much larger, more RAM usage). 
--> en_core_web_sm        (much smaller, less RAM usage).

Run 
-----------------------
python run.py