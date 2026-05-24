from executor import validate_read_only_sql


def test_sql_safety_allows_select() -> None:
    assert validate_read_only_sql("SELECT * FROM cloudtrail") == "SELECT * FROM cloudtrail"


def test_sql_safety_allows_with() -> None:
    sql = "WITH events AS (SELECT * FROM cloudtrail) SELECT * FROM events"
    assert validate_read_only_sql(sql) == sql


def test_sql_safety_rejects_destructive_statement() -> None:
    try:
        validate_read_only_sql("DROP TABLE cloudtrail")
    except ValueError as exc:
        assert "SELECT or WITH" in str(exc) or "blocked keyword" in str(exc)
    else:
        raise AssertionError("Expected destructive SQL to be rejected.")


def test_sql_safety_rejects_second_statement() -> None:
    try:
        validate_read_only_sql("SELECT * FROM cloudtrail; DELETE FROM cloudtrail")
    except ValueError as exc:
        assert "one statement" in str(exc)
    else:
        raise AssertionError("Expected multiple statements to be rejected.")
