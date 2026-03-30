from pipeline.ingestion_pipeline import run_ingestion
import json

if __name__ == "__main__":

    url = "https://ts.hust.edu.vn/training-cate/nganh-dao-tao-dai-hoc/ky-thuat-thuc-pham-chuong-trinh-tien-tien"

    doc = run_ingestion(url)

    print(json.dumps(doc.model_dump(), indent=2, ensure_ascii=False))