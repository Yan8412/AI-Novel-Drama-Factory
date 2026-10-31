from drama_deslop import scan_text


def test_clean_prose_is_not_over_limit() -> None:
    text = "林晚把合同翻到最后一页，签名的时间对不上出行记录。顾沉没说话。"
    report = scan_text(text, title="clean")
    assert report.grade == "clean"
    assert report.over_limit is False
    assert report.as_review_issues() == []
    assert "未发现" in report.to_markdown()


def test_clustered_adverbs_and_academic_terms_report_evidence() -> None:
    text = (
        "她微微点头，又微微侧过身，再微微停住。"
        "不难看出这就是答案。他心中暗道不行，又心中暗道再等，还心中暗道算了。"
    )
    report = scan_text(text, title="sloppy")
    assert report.over_limit is True
    assert report.grade in {"mid", "heavy", "light"}
    issues = report.as_review_issues()
    assert issues
    payload = report.to_payload()
    assert payload["title"] == "sloppy"
    hits = payload["hits"]
    assert isinstance(hits, list)
    assert any(
        isinstance(hit, dict) and hit.get("rule_id") == "weak_adverb" and hit.get("over_limit")
        for hit in hits
    )
    assert any(
        isinstance(hit, dict) and hit.get("rule_id") == "academic" and hit.get("over_limit")
        for hit in hits
    )
    assert any(
        isinstance(hit, dict) and hit.get("rule_id") == "mind_tell" and hit.get("over_limit")
        for hit in hits
    )
    assert any("微微" in ev for hit in report.hits for ev in hit.evidence)
    assert any("deslop" in issue.message for issue in issues)


def test_single_hit_is_not_a_defect() -> None:
    text = "她在门口停了一下，微微皱眉，然后推门进去把灯打开。"
    report = scan_text(text)
    adverb = next((hit for hit in report.hits if hit.rule_id == "weak_adverb"), None)
    if adverb is not None:
        assert adverb.count == 1
        assert adverb.over_limit is False
    assert all(not hit.over_limit or hit.severity != "hard" for hit in report.hits)
