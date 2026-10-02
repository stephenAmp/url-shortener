# Pagination in this URL shortener

`GET /urls/` returns URLs in pages. The route is in `app/api/routes/urls.py`; `UrlService.get_urls` in `app/services/url.py` builds the database query.

## 1. Request a page

```text
GET /urls/?page=2&limit=10
```

- `page` starts at **1** and defaults to 1.
- `limit` is the number of URLs per page. It defaults to 10 and must be between 1 and 100.
- Optional filters are `q` (short code or original URL), `is_active`, `created_from`, and `created_before`. For example: `GET /urls/?page=1&limit=10&is_active=true&q=docs`.

The route validates `page` and `limit` with FastAPI `Query`, then passes them to `get_urls`.

## 2. How `get_urls` finds the page

The service applies the same filters to both the count query and the URL query. Its pagination calculation is:

```python
total = self.db.scalar(
    select(func.count()).select_from(Url).where(*filters)
) or 0

total_pages = (total + limit - 1) // limit if total > 0 else 0
page = min(page, total_pages) if total > 0 else 1
offset = (page - 1) * limit

urls = self.db.scalars(
    select(Url)
    .where(*filters)
    .order_by(Url.created_at.desc(), Url.uuid.desc())
    .offset(offset)
    .limit(limit)
).all()
```

1. `total` counts **matching** URLs, so filters also change the number of pages.
2. `total_pages` rounds up. For 23 matches with a limit of 10, there are 3 pages.
3. `min(page, total_pages)` moves a request for page 7 back to page 3 when page 3 is the last page.
4. `offset` skips earlier rows; `limit` fetches only this page. Ordering by creation time and UUID gives a consistent order when timestamps match.

## 3. Read the response

The response has `data` (the URLs on this page) and `pagination`:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 0,
    "total_pages": 0
  }
}
```

This example is the **no matches** case. With matches, `data` contains URL objects. Use the returned `pagination.page` as the current page, because the server may have moved a requested page back to the last available one.

## 4. Use it in the frontend

- When search or filters change, request page **1** again.
- Show page numbers from 1 through `total_pages`.
- Disable **Previous** on page 1. Disable **Next** when `page >= total_pages`.
- When `total_pages` is 0, show an empty state instead of page buttons.

The list route is also limited to 20 requests per IP per minute; see [RateLimiting.md](RateLimiting.md).
