Run in sequence

pip install -r requirements.txt

python make_gold_template.py --input-csv "Community Medicine Experience Survey _ Ulat sa Epekto ng Gamot (Responses) - Form Responses 1.csv" --output-jsonl gold_template.jsonl

python main.py --input-csv "Community Medicine Experience Survey _ Ulat sa Epekto ng Gamot (Responses) - Form Responses 1.csv" --output-dir outputs

python main.py --input-csv "Community Medicine Experience Survey _ Ulat sa Epekto ng Gamot (Responses) - Form Responses 1.csv" --output-dir outputs --gold-jsonl gold_template.jsonl