from io_utils import load_dataset

df = load_dataset(
    "Community Medicine Experience Survey _ Ulat sa Epekto ng Gamot (Responses) - Form Responses 1.csv",
    verbose=True,
)

print(df[["case_id", "text_report", "medicine_checkbox"]].head(5).to_string())