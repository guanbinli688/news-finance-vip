from news_finance_v2.fetch import FetchResult, source_coverage


def test_source_coverage_counts_only_success():
    results = [FetchResult("a", "SUCCESS"), FetchResult("b", "HTTP_401")]
    assert source_coverage(results) == .5
