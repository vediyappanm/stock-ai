"""
Module:      tests.test_stock_domain
Purpose:     Unit tests for stock domain models
"""

# Standard Library
from datetime import datetime, timedelta

# Third Party
import pytest

# Local / Internal
from stock_domain.models import (
    EnsemblePrediction,
    ModelCacheMetadata,
    ModelMetrics,
    ModelSignature,
    ModelType,
    PredictionStatus,
    Result,
    ResultMetadata,
    SingleModelPrediction,
)


class TestResultMetadata:
    """Test ResultMetadata validation."""

    def test_valid_metadata_creation(self):
        """Happy path: valid metadata creation."""
        metadata = ResultMetadata(
            correlation_id="test-123",
            source="test_source"
        )
        assert metadata.correlation_id == "test-123"
        assert metadata.source == "test_source"

    def test_empty_correlation_id_raises(self):
        """Error path: empty correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="correlation_id cannot be empty"):
            ResultMetadata(correlation_id="", source="test")

    def test_negative_retry_count_raises(self):
        """Error path: negative retry_count raises ValueError."""
        with pytest.raises(ValueError, match="retry_count cannot be negative"):
            ResultMetadata(correlation_id="test", source="test", retry_count=-1)


class TestResult:
    """Test Result wrapper."""

    def test_successful_result(self):
        """Happy path: successful result with data."""
        result = Result(success=True, data=100.5)
        assert result.success is True
        assert result.data == 100.5
        assert result.unwrap() == 100.5

    def test_failed_result_requires_error_message(self):
        """Error path: failed result without error_message raises."""
        with pytest.raises(ValueError, match="Failed Result must include error_message"):
            Result(success=False)

    def test_unwrap_on_failed_result_raises(self):
        """Error path: unwrap on failed result raises RuntimeError."""
        result = Result(
            success=False,
            error_code="PREDICTION_ERROR",
            error_message="Model failed"
        )
        with pytest.raises(RuntimeError, match=r"\[PREDICTION_ERROR\] Model failed"):
            result.unwrap()


class TestModelSignature:
    """Test ModelSignature validation."""

    def test_valid_signature(self):
        """Happy path: valid signature creation."""
        sig = ModelSignature(
            last_date="2024-01-01",
            row_count=100,
            symbol="AAPL"
        )
        assert sig.last_date == "2024-01-01"
        assert sig.row_count == 100
        assert sig.symbol == "AAPL"

    def test_empty_last_date_raises(self):
        """Error path: empty last_date raises ValueError."""
        with pytest.raises(ValueError, match="last_date cannot be empty"):
            ModelSignature(last_date="", row_count=100, symbol="AAPL")

    def test_negative_row_count_raises(self):
        """Error path: negative row_count raises ValueError."""
        with pytest.raises(ValueError, match="row_count cannot be negative"):
            ModelSignature(last_date="2024-01-01", row_count=-1, symbol="AAPL")

    def test_empty_symbol_raises(self):
        """Error path: empty symbol raises ValueError."""
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            ModelSignature(last_date="2024-01-01", row_count=100, symbol="")


class TestModelMetrics:
    """Test ModelMetrics validation."""

    def test_valid_metrics(self):
        """Happy path: valid metrics creation."""
        metrics = ModelMetrics(
            residual_std=1.5,
            mae=0.5,
            rmse=0.8,
            r2_score=0.95
        )
        assert metrics.residual_std == 1.5
        assert metrics.mae == 0.5

    def test_negative_residual_std_raises(self):
        """Error path: negative residual_std raises ValueError."""
        with pytest.raises(ValueError, match="residual_std cannot be negative"):
            ModelMetrics(residual_std=-1.0)


class TestSingleModelPrediction:
    """Test SingleModelPrediction validation."""

    def test_valid_prediction(self):
        """Happy path: valid prediction creation."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.5,
            metrics=metrics
        )
        assert pred.model_type == ModelType.XGBOOST
        assert pred.prediction == 150.5

    def test_negative_prediction_raises(self):
        """Error path: negative prediction raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        with pytest.raises(ValueError, match="prediction cannot be negative"):
            SingleModelPrediction(
                model_type=ModelType.XGBOOST,
                prediction=-10.0,
                metrics=metrics
            )


class TestEnsemblePrediction:
    """Test EnsemblePrediction validation."""

    def test_valid_ensemble_prediction(self):
        """Happy path: valid ensemble prediction."""
        metrics = ModelMetrics(residual_std=1.0)
        xgb = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        rf = SingleModelPrediction(
            model_type=ModelType.RANDOM_FOREST,
            prediction=151.0,
            metrics=metrics
        )
        lstm = SingleModelPrediction(
            model_type=ModelType.LSTM,
            prediction=149.0,
            metrics=metrics
        )

        ensemble = EnsemblePrediction(
            symbol="AAPL",
            point_estimate=150.0,
            lower_bound=145.0,
            upper_bound=155.0,
            confidence_level=0.95,
            xgb_prediction=xgb,
            rf_prediction=rf,
            lstm_prediction=lstm,
            status=PredictionStatus.SUCCESS
        )
        assert ensemble.symbol == "AAPL"
        assert ensemble.point_estimate == 150.0

    def test_empty_symbol_raises(self):
        """Error path: empty symbol raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            EnsemblePrediction(
                symbol="",
                point_estimate=150.0,
                lower_bound=145.0,
                upper_bound=155.0,
                confidence_level=0.95,
                xgb_prediction=pred,
                rf_prediction=pred,
                lstm_prediction=pred,
                status=PredictionStatus.SUCCESS
            )

    def test_symbol_too_long_raises(self):
        """Error path: symbol exceeding max length raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        long_symbol = "A" * 21
        with pytest.raises(ValueError, match="symbol too long"):
            EnsemblePrediction(
                symbol=long_symbol,
                point_estimate=150.0,
                lower_bound=145.0,
                upper_bound=155.0,
                confidence_level=0.95,
                xgb_prediction=pred,
                rf_prediction=pred,
                lstm_prediction=pred,
                status=PredictionStatus.SUCCESS
            )

    def test_invalid_confidence_level_raises(self):
        """Error path: confidence_level outside valid range raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        with pytest.raises(ValueError, match="confidence_level must be between"):
            EnsemblePrediction(
                symbol="AAPL",
                point_estimate=150.0,
                lower_bound=145.0,
                upper_bound=155.0,
                confidence_level=1.5,
                xgb_prediction=pred,
                rf_prediction=pred,
                lstm_prediction=pred,
                status=PredictionStatus.SUCCESS
            )

    def test_lower_bound_exceeds_point_estimate_raises(self):
        """Error path: lower_bound > point_estimate raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        with pytest.raises(ValueError, match="lower_bound.*cannot exceed"):
            EnsemblePrediction(
                symbol="AAPL",
                point_estimate=150.0,
                lower_bound=155.0,
                upper_bound=160.0,
                confidence_level=0.95,
                xgb_prediction=pred,
                rf_prediction=pred,
                lstm_prediction=pred,
                status=PredictionStatus.SUCCESS
            )

    def test_upper_bound_less_than_point_estimate_raises(self):
        """Error path: upper_bound < point_estimate raises ValueError."""
        metrics = ModelMetrics(residual_std=1.0)
        pred = SingleModelPrediction(
            model_type=ModelType.XGBOOST,
            prediction=150.0,
            metrics=metrics
        )
        with pytest.raises(ValueError, match="upper_bound.*cannot be less than"):
            EnsemblePrediction(
                symbol="AAPL",
                point_estimate=150.0,
                lower_bound=145.0,
                upper_bound=145.0,
                confidence_level=0.95,
                xgb_prediction=pred,
                rf_prediction=pred,
                lstm_prediction=pred,
                status=PredictionStatus.SUCCESS
            )


class TestModelCacheMetadata:
    """Test ModelCacheMetadata validation."""

    def test_valid_cache_metadata(self):
        """Happy path: valid cache metadata creation."""
        sig = ModelSignature(last_date="2024-01-01", row_count=100, symbol="AAPL")
        metrics = ModelMetrics(residual_std=1.0)
        now = datetime.utcnow()

        cache_meta = ModelCacheMetadata(
            signature=sig,
            xgb_metrics=metrics,
            rf_metrics=metrics,
            lstm_metrics=metrics,
            feature_importance={"feature1": 0.5},
            created_at=now,
            last_accessed=now
        )
        assert cache_meta.signature.symbol == "AAPL"

    def test_future_created_at_raises(self):
        """Error path: created_at in future raises ValueError."""
        sig = ModelSignature(last_date="2024-01-01", row_count=100, symbol="AAPL")
        metrics = ModelMetrics(residual_std=1.0)
        future = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError, match="created_at cannot be in the future"):
            ModelCacheMetadata(
                signature=sig,
                xgb_metrics=metrics,
                rf_metrics=metrics,
                lstm_metrics=metrics,
                feature_importance={},
                created_at=future,
                last_accessed=datetime.utcnow()
            )
