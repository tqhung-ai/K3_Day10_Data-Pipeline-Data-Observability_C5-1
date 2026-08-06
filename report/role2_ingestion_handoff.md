# Vai trò 2 — Bàn giao Crossref ingestion (CP0–CP1)

## Contract nguồn

- Endpoint: `https://api.crossref.org/works`
- Query: `agentic retrieval augmented generation large language model`
- Filter used for this snapshot: `from-pub-date:2026-02-07,has-abstract:true`
- Requested rows: `24`
- Document ID ổn định: DOI chuẩn hóa (trim, bỏ prefix URL DOI, chuyển lowercase)

Parser chỉ bỏ record không thể truy vết an toàn do thiếu DOI hoặc title. Metadata tùy chọn được
giữ dưới dạng chuỗi/list rỗng để người phụ trách cleaning tự áp dụng và báo cáo quality gate mà
không bịa dữ liệu nguồn.

## Artifact bàn giao cho cleaning

| Artifact | Ý nghĩa |
| --- | --- |
| `data/raw/crossref_response.json` | JSON payload nguồn, được lưu trước khi parse |
| `data/raw/crossref_records.json` | Danh sách đã parse theo contract `PaperRecord` gồm 11 field |

Kết quả xác minh snapshot ngày 2026-08-06:

- Số item raw: `24`
- Số record đã parse: `24`
- Số `paper_id` unique: `24`
- Số record bị loại lúc parse: `0`
- Thiếu summary/authors/published: `0/0/0`
- Thiếu categories: `24`
- Parse lại response và so với records đã lưu: khớp chính xác (`True`)

Sample bàn giao:

```text
paper_id: 10.47576/2949-1894.2026.7.7.023
published: 2026-06-15
authors: 2
```

SHA-256 để nhận diện đúng snapshot:

```text
crossref_response.json  1DC4EF94694D97CFB26BF07E0D97A1DC661F3C62D3127D561DF1629BE74DD387
crossref_records.json   DFA730DA4DCB14A6ACCB35B2DA1EBC1806B2010B0A3E08EB3EE0D64A870E01F1
```

Crossref không cung cấp `subject` cho tập kết quả này. Cleaning cần giữ list category rỗng và báo
cáo missingness. Evaluation không nên tạo câu hỏi category từ snapshot này, trừ khi cả nhóm thống
nhất đổi source contract rồi dựng lại baseline một lần.

## Quy ước field

- `title` and `summary`: remove JATS/HTML markup, decode entities, normalize whitespace.
- `authors`: join `given` and `family`; support organization `name`; remove empty duplicates.
- `categories`: normalize/deduplicate `subject`; the first value is the internal
  `primary_category` convention, not a Crossref primary-subject guarantee.
- `published`: `published` → `published-print` → `published-online` → `issued` → `created`;
  ngày thiếu tháng/ngày được chuẩn hóa về ngày đầu tiên của kỳ.
- `updated`: `deposited` → `indexed` → `published` fallback.
- `abs_url`: Crossref `URL`, falling back to `https://doi.org/{paper_id}`.
- `pdf_url`: first `link` identified as PDF; an empty value does not imply the paper has no PDF.
- `comment`: empty because Crossref has no equivalent field in this lab contract.

## Blocker đã xử lý

Crossref trả HTTP `406 Not Acceptable` khi gửi MIME phản hồi
`application/vnd.crossref-api-message+json` làm request `Accept`. API trả JSON mặc định nên code
đã bỏ header này, giữ `User-Agent`, sau đó fetch thành công 24 record.

## Xác minh mà không refresh nguồn

```powershell
uv run python -c "from core.config import load_settings; from ingestion.crossref import load_raw_records; s=load_settings(); rows=load_raw_records(s.paths.raw_records_json); print(len(rows), len({r.paper_id for r in rows}), rows[0].paper_id)"
uv run python -m unittest discover -s tests -v
```

Không gọi lại `fetch_source_records` trong lúc so sánh baseline/corrupted/repaired. Người tích hợp
phải load snapshot này khi `refresh_source` là `false`.
