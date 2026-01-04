"""
Test cases for the Observer pattern implementation.
"""

from datetime import datetime, timedelta

import pytest

from squish.observer import (
    CompositeProgressObserver,
    EventDispatcher,
    FilteringProgressObserver,
    IProgressObserver,
    NullProgressObserver,
    ObserverNotificationError,
    ObserverRegistrationError,
    OperationEvent,
    OperationType,
    ProgressInfo,
    ProgressObserverAdapter,
    ProgressState,
    ProgressSubject,
)


class TestProgressInfo:
    """Test cases for ProgressInfo dataclass."""

    def test_progress_info_creation(self):
        """Test creating ProgressInfo with all fields."""
        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50.0,
            current=100,
            total=200,
            message="Building...",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            elapsed_time=timedelta(seconds=10),
            estimated_remaining=timedelta(seconds=10),
            speed=10.0,
            metadata={"key": "value"},
        )

        assert progress.operation_type == OperationType.BUILD
        assert progress.state == ProgressState.IN_PROGRESS
        assert progress.percentage == 50.0
        assert progress.current == 100
        assert progress.total == 200
        assert progress.message == "Building..."
        assert progress.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert progress.elapsed_time == timedelta(seconds=10)
        assert progress.estimated_remaining == timedelta(seconds=10)
        assert progress.speed == 10.0
        assert progress.metadata == {"key": "value"}

    def test_progress_info_defaults(self):
        """Test ProgressInfo with default values."""
        progress = ProgressInfo(
            operation_type=OperationType.EXTRACT, state=ProgressState.NOT_STARTED
        )

        assert progress.percentage == 0.0
        assert progress.current == 0
        assert progress.total == 0
        assert progress.message == ""
        assert progress.metadata == {}
        assert isinstance(progress.timestamp, datetime)
        assert isinstance(progress.elapsed_time, timedelta)
        assert progress.estimated_remaining is None
        assert progress.speed is None

    def test_progress_info_methods(self):
        """Test ProgressInfo helper methods."""
        # Test complete states
        complete_progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.COMPLETED
        )
        assert complete_progress.is_complete()
        assert not complete_progress.is_active()

        # Test active state
        active_progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )
        assert not active_progress.is_complete()
        assert active_progress.is_active()

        # Test progress ratio
        assert (
            ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.COMPLETED,
                percentage=100.0,
            ).get_progress_ratio()
            == 1.0
        )
        assert (
            ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                percentage=75.0,
            ).get_progress_ratio()
            == 0.75
        )

        # Test ratio clamping
        assert (
            ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                percentage=150.0,
            ).get_progress_ratio()
            == 1.0
        )

        assert (
            ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                percentage=-10.0,
            ).get_progress_ratio()
            == 0.0
        )


class TestOperationEvent:
    """Test cases for OperationEvent dataclass."""

    def test_operation_event_creation(self):
        """Test creating OperationEvent with all fields."""
        event = OperationEvent(
            event_type="test_event",
            operation_type=OperationType.MOUNT,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            data={"key": "value"},
            source="test_source",
        )

        assert event.event_type == "test_event"
        assert event.operation_type == OperationType.MOUNT
        assert event.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert event.data == {"key": "value"}
        assert event.source == "test_source"

    def test_operation_event_defaults(self):
        """Test OperationEvent with default values."""
        event = OperationEvent(
            event_type="simple_event", operation_type=OperationType.UNMOUNT
        )

        assert event.data == {}
        assert event.source == "unknown"
        assert isinstance(event.timestamp, datetime)


class MockProgressObserver(IProgressObserver):
    """Mock implementation of IProgressObserver for testing."""

    def __init__(self):
        self.progress_updates = []
        self.completions = []
        self.cancellations = []
        self.errors = []
        self.events = []

    def on_progress_update(self, progress: ProgressInfo) -> None:
        self.progress_updates.append(progress)

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        self.completions.append((progress, success))

    def on_cancellation(self, progress: ProgressInfo) -> None:
        self.cancellations.append(progress)

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        self.errors.append((progress, error))

    def on_event(self, event: OperationEvent) -> None:
        self.events.append(event)


class TestProgressSubject:
    """Test cases for ProgressSubject class."""

    def test_attach_and_detach_observers(self):
        """Test attaching and detaching observers."""
        subject = ProgressSubject()
        observer1 = MockProgressObserver()
        observer2 = MockProgressObserver()

        # Test initial state
        assert subject.get_observer_count() == 0

        # Attach observers
        subject.attach(observer1)
        subject.attach(observer2)
        assert subject.get_observer_count() == 2

        # Detach one observer
        subject.detach(observer1)
        assert subject.get_observer_count() == 1

        # Detach all
        subject.detach_all()
        assert subject.get_observer_count() == 0

    def test_attach_duplicate_observer(self):
        """Test that attaching duplicate observer raises error."""
        subject = ProgressSubject()
        observer = MockProgressObserver()

        subject.attach(observer)

        with pytest.raises(ObserverRegistrationError):
            subject.attach(observer)

    def test_notify_progress_update(self):
        """Test notifying observers of progress updates."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50.0,
        )

        subject.notify_progress(progress)

        assert len(observer.progress_updates) == 1
        assert observer.progress_updates[0] == progress

    def test_notify_completion(self):
        """Test notifying observers of completion."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.notify_completion(True)

        # Should create completion progress from last progress
        assert len(observer.completions) == 1
        completion_progress, success = observer.completions[0]
        assert success is True
        assert completion_progress.state == ProgressState.COMPLETED
        assert completion_progress.percentage == 100.0

    def test_notify_completion_without_prior_progress(self):
        """Test completion notification when no prior progress exists."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.notify_completion(False)

        assert len(observer.completions) == 1
        completion_progress, success = observer.completions[0]
        assert success is False
        assert completion_progress.state == ProgressState.FAILED
        assert completion_progress.operation_type == OperationType.UNKNOWN

    def test_notify_cancellation(self):
        """Test notifying observers of cancellation."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        progress = ProgressInfo(
            operation_type=OperationType.EXTRACT,
            state=ProgressState.IN_PROGRESS,
            percentage=75.0,
        )
        subject.notify_progress(progress)

        subject.notify_cancellation()

        assert len(observer.cancellations) == 1
        cancellation_progress = observer.cancellations[0]
        assert cancellation_progress.state == ProgressState.CANCELLED

    def test_notify_error(self):
        """Test notifying observers of errors."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        error = ValueError("Test error")
        subject.notify_error(error)

        assert len(observer.errors) == 1
        error_progress, reported_error = observer.errors[0]
        assert reported_error == error
        assert error_progress.state == ProgressState.FAILED
        assert error_progress.message == str(error)

    def test_notify_event(self):
        """Test notifying observers of events."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        event = OperationEvent(
            event_type="test_event", operation_type=OperationType.LIST
        )

        subject.notify_event(event)

        assert len(observer.events) == 1
        assert observer.events[0] == event

    def test_observer_notification_error(self):
        """Test error handling when observer notification fails."""
        subject = ProgressSubject()

        class FailingObserver(IProgressObserver):
            def on_progress_update(self, progress: ProgressInfo) -> None:
                raise RuntimeError("Observer failed")

            def on_completion(self, progress: ProgressInfo, success: bool) -> None:
                pass

            def on_cancellation(self, progress: ProgressInfo) -> None:
                pass

            def on_error(self, progress: ProgressInfo, error: Exception) -> None:
                pass

        failing_observer = FailingObserver()
        subject.attach(failing_observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )

        with pytest.raises(ObserverNotificationError):
            subject.notify_progress(progress)

    def test_start_operation(self):
        """Test starting an operation."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.start_operation(OperationType.MOUNT)

        assert len(observer.events) == 1
        event = observer.events[0]
        assert event.event_type == "operation_start"
        assert event.operation_type == OperationType.MOUNT
        assert "timestamp" in event.data

    def test_update_progress(self):
        """Test updating progress with helper method."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.start_operation(OperationType.BUILD)

        progress = subject.update_progress(
            operation_type=OperationType.BUILD,
            percentage=50.0,
            current=100,
            total=200,
            message="Building files...",
        )

        assert len(observer.progress_updates) == 1
        assert progress.percentage == 50.0
        assert progress.current == 100
        assert progress.total == 200
        assert progress.message == "Building files..."
        assert progress.operation_type == OperationType.BUILD
        assert progress.state == ProgressState.IN_PROGRESS
        assert progress.elapsed_time > timedelta()
        assert progress.estimated_remaining is not None
        assert progress.speed is not None

    def test_complete_operation(self):
        """Test completing an operation."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.start_operation(OperationType.EXTRACT)
        subject.update_progress(
            operation_type=OperationType.EXTRACT, percentage=80.0, current=80, total=100
        )

        subject.complete_operation(True)

        assert len(observer.completions) == 1
        completion_progress, success = observer.completions[0]
        assert success is True
        assert completion_progress.state == ProgressState.COMPLETED
        assert completion_progress.percentage == 100.0

    def test_cancel_operation(self):
        """Test cancelling an operation."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.start_operation(OperationType.CHECKSUM)
        subject.update_progress(
            operation_type=OperationType.CHECKSUM,
            percentage=30.0,
            current=30,
            total=100,
        )

        subject.cancel_operation()

        assert len(observer.cancellations) == 1
        cancellation_progress = observer.cancellations[0]
        assert cancellation_progress.state == ProgressState.CANCELLED

    def test_report_error(self):
        """Test reporting an error."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        subject.start_operation(OperationType.LIST)

        error = IOError("File not found")
        subject.report_error(error)

        assert len(observer.errors) == 1
        error_progress, reported_error = observer.errors[0]
        assert reported_error == error
        assert error_progress.state == ProgressState.FAILED
        assert error_progress.message == str(error)


class TestCompositeProgressObserver:
    """Test cases for CompositeProgressObserver class."""

    def test_composite_observer_delegation(self):
        """Test that composite observer delegates to all observers."""
        observer1 = MockProgressObserver()
        observer2 = MockProgressObserver()

        composite = CompositeProgressObserver()
        composite.add_observer(observer1)
        composite.add_observer(observer2)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50.0,
        )

        # Test progress update
        composite.on_progress_update(progress)
        assert len(observer1.progress_updates) == 1
        assert len(observer2.progress_updates) == 1

        # Test completion
        composite.on_completion(progress, True)
        assert len(observer1.completions) == 1
        assert len(observer2.completions) == 1

        # Test cancellation
        composite.on_cancellation(progress)
        assert len(observer1.cancellations) == 1
        assert len(observer2.cancellations) == 1

        # Test error
        error = ValueError("Test error")
        composite.on_error(progress, error)
        assert len(observer1.errors) == 1
        assert len(observer2.errors) == 1

        # Test event
        event = OperationEvent("test", OperationType.BUILD)
        composite.on_event(event)
        assert len(observer1.events) == 1
        assert len(observer2.events) == 1

    def test_composite_observer_removal(self):
        """Test removing observers from composite."""
        observer1 = MockProgressObserver()
        observer2 = MockProgressObserver()

        composite = CompositeProgressObserver()
        composite.add_observer(observer1)
        composite.add_observer(observer2)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )

        # Remove one observer
        composite.remove_observer(observer1)

        composite.on_progress_update(progress)

        # Only observer2 should receive the update
        assert len(observer1.progress_updates) == 0
        assert len(observer2.progress_updates) == 1


class TestFilteringProgressObserver:
    """Test cases for FilteringProgressObserver class."""

    def test_filtering_observer_thresholds(self):
        """Test filtering based on percentage and time thresholds."""
        delegate = MockProgressObserver()

        # Create observer with strict filtering
        filtering_observer = FilteringProgressObserver(
            delegate=delegate,
            min_percentage_change=5.0,  # 5% minimum change
            min_time_interval=0.5,  # 0.5 second minimum interval
        )

        # These should be filtered out (small changes)
        for i in range(1, 5):
            progress = ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                percentage=float(i),
            )
            filtering_observer.on_progress_update(progress)

        # Should have no updates yet
        assert len(delegate.progress_updates) == 0

        # This should trigger an update (5% change)
        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=5.0,
        )
        filtering_observer.on_progress_update(progress)

        assert len(delegate.progress_updates) == 1

    def test_filtering_observer_always_notifies_completion(self):
        """Test that filtering observer always notifies completion."""
        delegate = MockProgressObserver()

        filtering_observer = FilteringProgressObserver(
            delegate=delegate,
            min_percentage_change=100.0,  # Very high threshold
        )

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=1.0,
        )

        # Progress updates should be filtered
        filtering_observer.on_progress_update(progress)
        assert len(delegate.progress_updates) == 0

        # But completion should always be notified
        filtering_observer.on_completion(progress, True)
        assert len(delegate.completions) == 1

        # And errors should always be notified
        error = ValueError("Test error")
        filtering_observer.on_error(progress, error)
        assert len(delegate.errors) == 1

        # And cancellations should always be notified
        filtering_observer.on_cancellation(progress)
        assert len(delegate.cancellations) == 1


class TestNullProgressObserver:
    """Test cases for NullProgressObserver class."""

    def test_null_observer_does_nothing(self):
        """Test that null observer doesn't raise errors."""
        observer = NullProgressObserver()

        progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )

        # All methods should do nothing without raising errors
        observer.on_progress_update(progress)
        observer.on_completion(progress, True)
        observer.on_cancellation(progress)
        observer.on_error(progress, ValueError("Test"))
        observer.on_event(OperationEvent("test", OperationType.BUILD))


class TestProgressObserverAdapter:
    """Test cases for ProgressObserverAdapter class."""

    def test_adapter_conversion(self, mocker):
        """Test adapting ProgressInfo to different format."""
        target_observer = mocker.MagicMock()

        def adapter_func(progress: ProgressInfo) -> dict:
            return {
                "type": progress.operation_type.name,
                "percent": progress.percentage,
                "message": progress.message,
            }

        adapter = ProgressObserverAdapter(adapter_func)
        adapter.add_target_observer(target_observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50.0,
            message="Building...",
        )

        adapter.on_progress_update(progress)

        # Verify the adapted format was passed to target observer
        target_observer.assert_called_once_with(
            {"type": "BUILD", "percent": 50.0, "message": "Building..."}
        )

    def test_adapter_completion(self, mocker):
        """Test adapting completion notifications."""
        target_observer = mocker.MagicMock()

        def adapter_func(progress: ProgressInfo) -> dict:
            return {"percent": progress.percentage}

        adapter = ProgressObserverAdapter(adapter_func)
        adapter.add_target_observer(target_observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.COMPLETED,
            percentage=100.0,
        )

        adapter.on_completion(progress, True)

        target_observer.assert_called_once_with(
            {"progress": {"percent": 100.0}, "success": True}
        )

    def test_adapter_error(self, mocker):
        """Test adapting error notifications."""
        target_observer = mocker.MagicMock()

        def adapter_func(progress: ProgressInfo) -> dict:
            return {"percent": progress.percentage}

        adapter = ProgressObserverAdapter(adapter_func)
        adapter.add_target_observer(target_observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.FAILED,
            percentage=50.0,
        )

        error = ValueError("Test error")
        adapter.on_error(progress, error)

        target_observer.assert_called_once_with(
            {"progress": {"percent": 50.0}, "error": "Test error"}
        )


class TestEventDispatcher:
    """Test cases for EventDispatcher class."""

    def test_event_dispatcher_basic(self, mocker):
        """Test basic event dispatching."""
        dispatcher = EventDispatcher()

        listener1 = mocker.MagicMock()
        listener2 = mocker.MagicMock()

        dispatcher.add_listener("test_event", listener1)
        dispatcher.add_listener("test_event", listener2)

        event = OperationEvent("test_event", OperationType.BUILD)
        dispatcher.dispatch(event)

        listener1.assert_called_once_with(event)
        listener2.assert_called_once_with(event)

    def test_event_dispatcher_wildcard(self, mocker):
        """Test wildcard event listeners."""
        dispatcher = EventDispatcher()

        specific_listener = mocker.MagicMock()
        wildcard_listener = mocker.MagicMock()

        dispatcher.add_listener("specific_event", specific_listener)
        dispatcher.add_listener("*", wildcard_listener)

        # Dispatch specific event
        specific_event = OperationEvent("specific_event", OperationType.BUILD)
        dispatcher.dispatch(specific_event)

        specific_listener.assert_called_once_with(specific_event)
        wildcard_listener.assert_called_once_with(specific_event)

        # Dispatch different event
        other_event = OperationEvent("other_event", OperationType.EXTRACT)
        dispatcher.dispatch(other_event)

        # Only wildcard should be called
        assert specific_listener.call_count == 1  # Only called for specific_event
        assert wildcard_listener.call_count == 2  # Called for both events

    def test_event_dispatcher_removal(self, mocker):
        """Test removing listeners."""
        dispatcher = EventDispatcher()

        listener = mocker.MagicMock()
        dispatcher.add_listener("test_event", listener)

        event = OperationEvent("test_event", OperationType.BUILD)
        dispatcher.dispatch(event)

        assert listener.call_count == 1

        # Remove listener
        dispatcher.remove_listener("test_event", listener)
        dispatcher.dispatch(event)

        # Should not be called again
        assert listener.call_count == 1

    def test_event_dispatcher_error_handling(self, mocker):
        """Test that dispatcher continues after listener errors."""
        dispatcher = EventDispatcher()

        def failing_listener(event):
            raise RuntimeError("Listener failed")

        good_listener = mocker.MagicMock()

        dispatcher.add_listener("test_event", failing_listener)
        dispatcher.add_listener("test_event", good_listener)

        event = OperationEvent("test_event", OperationType.BUILD)

        # Should not raise, and good listener should still be called
        dispatcher.dispatch(event)

        good_listener.assert_called_once_with(event)

    def test_event_dispatcher_clear(self, mocker):
        """Test clearing all listeners."""
        dispatcher = EventDispatcher()

        listener1 = mocker.MagicMock()
        listener2 = mocker.MagicMock()

        dispatcher.add_listener("event1", listener1)
        dispatcher.add_listener("event2", listener2)

        # Clear all listeners
        dispatcher.clear()

        # Dispatch events - no listeners should be called
        dispatcher.dispatch(OperationEvent("event1", OperationType.BUILD))
        dispatcher.dispatch(OperationEvent("event2", OperationType.BUILD))

        assert listener1.call_count == 0
        assert listener2.call_count == 0


class TestObserverPatternIntegration:
    """Integration tests for observer pattern components."""

    def test_complete_operation_lifecycle(self):
        """Test a complete operation lifecycle with observers."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        # Start operation
        subject.start_operation(OperationType.BUILD)
        assert len(observer.events) == 1
        assert observer.events[0].event_type == "operation_start"

        # Update progress multiple times
        for i in range(10, 100, 10):
            subject.update_progress(
                operation_type=OperationType.BUILD,
                percentage=float(i),
                current=i,
                total=100,
                message=f"Progress: {i}%",
            )

        assert len(observer.progress_updates) == 9

        # Complete operation
        subject.complete_operation(True)
        assert len(observer.completions) == 1

        # Verify final state
        final_progress, success = observer.completions[0]
        assert success is True
        assert final_progress.state == ProgressState.COMPLETED
        assert final_progress.percentage == 100.0

    def test_error_operation_lifecycle(self):
        """Test operation lifecycle with error."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        # Start and make some progress
        subject.start_operation(OperationType.EXTRACT)
        subject.update_progress(
            operation_type=OperationType.EXTRACT, percentage=50.0, current=50, total=100
        )

        # Report error
        error = IOError("Extraction failed")
        subject.report_error(error)

        # Verify error was reported
        assert len(observer.errors) == 1
        error_progress, reported_error = observer.errors[0]
        assert reported_error == error
        assert error_progress.state == ProgressState.FAILED
        assert error_progress.message == str(error)

    def test_cancellation_lifecycle(self):
        """Test operation cancellation lifecycle."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        # Start and make progress
        subject.start_operation(OperationType.MOUNT)
        subject.update_progress(
            operation_type=OperationType.MOUNT, percentage=25.0, current=25, total=100
        )

        # Cancel operation
        subject.cancel_operation()

        # Verify cancellation
        assert len(observer.cancellations) == 1
        cancellation_progress = observer.cancellations[0]
        assert cancellation_progress.state == ProgressState.CANCELLED
        assert cancellation_progress.percentage == 25.0


class TestObserverPatternEdgeCases:
    """Edge case tests for observer pattern."""

    def test_multiple_observers_error_handling(self):
        """Test error handling with multiple observers."""
        subject = ProgressSubject()

        class FailingObserver(IProgressObserver):
            def on_progress_update(self, progress: ProgressInfo) -> None:
                raise RuntimeError("Observer failed")

            def on_completion(self, progress: ProgressInfo, success: bool) -> None:
                pass

            def on_cancellation(self, progress: ProgressInfo) -> None:
                pass

            def on_error(self, progress: ProgressInfo, error: Exception) -> None:
                pass

        good_observer = MockProgressObserver()
        failing_observer = FailingObserver()

        subject.attach(good_observer)
        subject.attach(failing_observer)

        progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )

        # Should raise error but good observer should have been called first
        with pytest.raises(ObserverNotificationError):
            subject.notify_progress(progress)

        # The good observer should have been called before the error
        assert len(good_observer.progress_updates) == 1

    def test_empty_observer_list(self):
        """Test operations with no observers attached."""
        subject = ProgressSubject()

        progress = ProgressInfo(
            operation_type=OperationType.BUILD, state=ProgressState.IN_PROGRESS
        )

        # All operations should work fine with no observers
        subject.notify_progress(progress)
        subject.notify_completion(True)
        subject.notify_cancellation()
        subject.notify_error(ValueError("Test"))
        subject.notify_event(OperationEvent("test", OperationType.BUILD))

        # Should not raise any errors

    def test_rapid_progress_updates(self):
        """Test handling rapid progress updates."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        # Send many rapid updates
        for i in range(1000):
            progress = ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                percentage=float(i % 100),
                current=i,
                total=1000,
            )
            subject.notify_progress(progress)

        # Should handle all updates without error
        assert len(observer.progress_updates) == 1000

    def test_large_metadata(self):
        """Test handling large metadata in progress info."""
        subject = ProgressSubject()
        observer = MockProgressObserver()
        subject.attach(observer)

        # Create progress with large metadata
        large_metadata = {f"key_{i}": f"value_{i}" for i in range(1000)}

        progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50.0,
            metadata=large_metadata,
        )

        subject.notify_progress(progress)

        # Should handle large metadata without issues
        assert len(observer.progress_updates) == 1
        assert observer.progress_updates[0].metadata == large_metadata
