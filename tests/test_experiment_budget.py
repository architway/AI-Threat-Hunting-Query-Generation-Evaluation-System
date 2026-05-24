from experiments import enforce_request_budget, estimate_request_count


def test_experiment_estimates_worst_case_request_count() -> None:
    assert (
        estimate_request_count(
            model_count=2,
            strategy_count=2,
            hypothesis_count=3,
            repair_attempts=1,
        )
        == 24
    )


def test_real_experiment_refuses_to_exceed_request_budget() -> None:
    try:
        enforce_request_budget(
            estimated_requests=51,
            request_budget=50,
            use_mock=False,
        )
    except ValueError as exc:
        assert "exceed the real request budget" in str(exc)
    else:
        raise AssertionError("Expected real over-budget experiment to fail.")


def test_mock_experiment_ignores_request_budget() -> None:
    enforce_request_budget(
        estimated_requests=500,
        request_budget=1,
        use_mock=True,
    )
