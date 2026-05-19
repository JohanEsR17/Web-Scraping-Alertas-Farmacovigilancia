from pathlib import Path
import importlib

import content_extractor
import scraper
from scraper import (
    DRUGOFFICE_BASE_URL,
    DRUGOFFICE_SOURCE_ID,
    build_drugoffice_other_safety_alerts_url,
    clean_text,
    infer_alert_jurisdiction,
    is_drugoffice_media_prefix_excluded,
    map_drugoffice_prefix,
    parse_drugoffice_title_prefix,
    normalize_drugoffice_date,
    normalize_url,
    parse_drugoffice_other_safety_alerts_list,
    scrape_drugoffice_other_safety_alerts,
)


FIXTURES = Path(__file__).parent / "fixtures" / "drugoffice_other_safety_alerts"


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_helpers_normalize_text_url_date_and_jurisdiction():
    assert clean_text("  FDA\n  safety   alert ") == "FDA safety alert"
    assert normalize_url(DRUGOFFICE_BASE_URL, "/eps/news/item.html") == "https://www.drugoffice.gov.hk/eps/news/item.html"
    assert normalize_url(DRUGOFFICE_BASE_URL, "javascript:void(0)") is None
    assert normalize_drugoffice_date("19 May 2026") == "19-05-2026"
    assert normalize_drugoffice_date("not a date") is None
    assert infer_alert_jurisdiction("FDA warns about medicine") == "United States"


def test_drugoffice_title_prefix_parsing_and_mapping():
    assert parse_drugoffice_title_prefix("Australia: Drug safety update") == ("Australia", "Drug safety update")
    assert parse_drugoffice_title_prefix("The United States：Drug recall") == ("The United States", "Drug recall")
    assert parse_drugoffice_title_prefix("No colon here") == (None, "No colon here")

    assert map_drugoffice_prefix("Australia") == ("Australia", "TGA")
    assert map_drugoffice_prefix("The United Kingdom") == ("United Kingdom", "MHRA")
    assert map_drugoffice_prefix("The United States") == ("United States", "FDA")
    assert map_drugoffice_prefix("European Union") == ("European Union", "EMA")
    assert map_drugoffice_prefix("中國") == ("China", "NMPA")


def test_parser_emits_only_valid_primary_alerts():
    alerts = parse_drugoffice_other_safety_alerts_list(read_fixture("list_mixed.html"), DRUGOFFICE_BASE_URL)

    assert len(alerts) == 8

    assert alerts[0]["titulo"] == "Tranexamic acid alert"
    assert alerts[0]["fecha"] == "19-05-2026"
    assert alerts[0]["pais"] == "Australia"
    assert alerts[0]["institucion"] == "TGA"
    assert alerts[0]["source_id"] == DRUGOFFICE_SOURCE_ID
    assert alerts[0]["publisher_country"] == "Hong Kong"
    assert alerts[0]["alert_jurisdiction"] == "Australia"
    assert alerts[0]["pdf"] is None

    assert alerts[7]["pdf"] == alerts[7]["url"]


def test_parser_excludes_chinese_media_prefix():
    alerts = parse_drugoffice_other_safety_alerts_list(read_fixture("list_china_media_row.html"), DRUGOFFICE_BASE_URL)
    assert alerts == []

    prefix, _ = parse_drugoffice_title_prefix("中國內地傳媒: Some title")
    assert is_drugoffice_media_prefix_excluded(prefix) is True


def test_parser_accepts_iso_date_live_shape_row_and_normalizes_date():
    alerts = parse_drugoffice_other_safety_alerts_list(read_fixture("list_iso_date.html"), DRUGOFFICE_BASE_URL)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["fecha"] == "19-05-2026"
    assert alert["url"] == "https://www.drugoffice.gov.hk/eps/news/showNews/consumer/2026-05-19/en/57472.html"
    assert alert["titulo"] == "safety update on recalled device"


def test_parser_returns_empty_for_no_news():
    assert parse_drugoffice_other_safety_alerts_list(read_fixture("list_no_news.html"), DRUGOFFICE_BASE_URL) == []


def test_parser_skips_rows_with_missing_or_unusable_dates():
    html = read_fixture("list_missing_date_row.html")
    alerts = parse_drugoffice_other_safety_alerts_list(html, DRUGOFFICE_BASE_URL)

    assert alerts == []


def test_parser_skips_rows_with_only_related_links():
    html = read_fixture("list_related_only_row.html")
    alerts = parse_drugoffice_other_safety_alerts_list(html, DRUGOFFICE_BASE_URL)

    assert alerts == []


def test_parser_prefers_primary_link_when_related_link_is_first():
    html = read_fixture("list_related_first_row.html")
    alerts = parse_drugoffice_other_safety_alerts_list(html, DRUGOFFICE_BASE_URL)

    assert len(alerts) == 1
    assert alerts[0]["url"] == "https://www.drugoffice.gov.hk/eps/news/showNews/consumer/2026-05-13/en/67890.html"
    assert alerts[0]["titulo"] == "Actual primary alert"


def test_drugoffice_original_url_extraction_prefers_reference_phrase(monkeypatch):
    class Response:
        status_code = 200
        content = read_fixture("detail_original_source.html").encode("utf-8")

    monkeypatch.setattr(content_extractor.curl_requests, "get", lambda *args, **kwargs: Response())

    original = {
        "url": "https://www.drugoffice.gov.hk/eps/news/showNews/item.html",
        "pais": "Australia",
        "source_id": DRUGOFFICE_SOURCE_ID,
    }
    text = content_extractor.extract_content(original)

    assert text is not None
    assert original.get("url_fuente_original") == "https://www.example-authority.gov/alert/123"


def test_drugoffice_original_url_extraction_falls_back_to_first_external_link(monkeypatch):
    def extract_from_detail_html(html_content):
        class Response:
            status_code = 200
            content = (
                "<html><body><h1>Title</h1><td id='newsContent'>text</td>"
                "<a href='https://www.drugoffice.gov.hk/eps/news/inside.html'>inside</a>"
                "<a href='https://www.example-authority.gov/primary'>primary</a>"
                "<a href='https://www.other-authority.com/secondary'>secondary</a></body></html>"
            ).encode("utf-8")

        return Response()

    monkeypatch.setattr(content_extractor.curl_requests, "get", lambda *args, **kwargs: extract_from_detail_html(args[0]))

    item = {
        "url": "https://www.drugoffice.gov.hk/eps/news/showNews/item.html",
        "pais": "Australia",
        "source_id": DRUGOFFICE_SOURCE_ID,
    }

    content_extractor.extract_content(item)

    assert item["url_fuente_original"] == "https://www.example-authority.gov/primary"


def test_preferred_telegram_link_selection(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "dummy-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "dummy-chat")
    main = importlib.import_module("main")

    assert main.select_preferred_alert_link({"url_fuente_original": "https://authority", "url": "https://drugoffice", "pdf": "https://pdf"}) == "https://authority"
    assert main.select_preferred_alert_link({"url": "https://drugoffice", "pdf": "https://pdf"}) == "https://drugoffice"
    assert main.select_preferred_alert_link({"pdf": "https://pdf"}) == "https://pdf"
    assert main.select_preferred_alert_link({}) is None


def test_scraper_uses_current_year_url_and_injected_fetcher():
    class Response:
        status_code = 200
        content = read_fixture("list_no_news.html")

    requested_urls = []

    def fake_fetcher(url, **kwargs):
        requested_urls.append(url)
        return Response()

    assert scrape_drugoffice_other_safety_alerts(year=2026, fetcher=fake_fetcher) == []
    assert requested_urls == [build_drugoffice_other_safety_alerts_url(2026)]


def test_drugoffice_url_builder_uses_discovered_endpoint_pattern():
    assert build_drugoffice_other_safety_alerts_url(2026) == (
        "https://www.drugoffice.gov.hk/eps/news/listNews/en/healthcare_providers/8?search_year=2026"
    )


def test_drugoffice_request_uses_no_impersonate_when_not_using_curl_cffi(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        content = read_fixture("list_no_news.html")

    def legacy_fetcher(url, **kwargs):
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(scraper, "_HAS_CURL_CFFI_REQUESTS", False)
    assert scrape_drugoffice_other_safety_alerts(year=2026, fetcher=legacy_fetcher) == []
    assert calls and "impersonate" not in calls[0]


def test_drugoffice_detail_extraction_uses_title_and_news_content(monkeypatch):
    class Response:
        status_code = 200
        content = read_fixture("detail.html").encode("utf-8")

    monkeypatch.setattr(content_extractor.curl_requests, "get", lambda *args, **kwargs: Response())

    text = content_extractor.extract_content({
        "url": "https://www.drugoffice.gov.hk/eps/news/showNews/item.html",
        "pais": "Internacional",
        "source_id": DRUGOFFICE_SOURCE_ID,
    })

    assert text is not None
    assert "Other safety alert title" in text
    assert "safety issue affecting imported medicine" in text
