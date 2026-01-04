"""
Observer Pattern Implementation for SquishFS.

This module provides a comprehensive implementation of the Observer pattern
for progress tracking and event notification. It includes:

- IProgressObserver interface for progress observers
- ProgressSubject for managing and notifying observers
- ProgressInfo dataclass for progress information
- Event system for various operation events
- Error handling for observer notifications
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional


class ObserverError(Exception):
    """Base exception for observer pattern errors."""

    pass


class ObserverRegistrationError(ObserverError):
    """Exception raised when observer registration fails."""

    pass


class ObserverNotificationError(ObserverError):
    """Exception raised when observer notification fails."""

    pass


class ProgressState(Enum):
    """Enumeration of progress states."""

    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    PAUSED = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    FAILED = auto()


class OperationType(Enum):
    """Enumeration of operation types."""

    BUILD = auto()
    EXTRACT = auto()
    MOUNT = auto()
    UNMOUNT = auto()
    CHECKSUM = auto()
    LIST = auto()
    UNKNOWN = auto()


@dataclass
class ProgressInfo:
    """
    Data class containing progress information.

    Attributes:
        operation_type: Type of operation being performed
        state: Current state of the operation
        percentage: Progress percentage (0-100)
        current: Current progress value
        total: Total progress value
        message: Optional progress message
        timestamp: Timestamp of the progress update
        elapsed_time: Time elapsed since operation start
        estimated_remaining: Estimated time remaining
        speed: Current operation speed
        metadata: Additional metadata
    """

    operation_type: OperationType
    state: ProgressState
    percentage: float = 0.0
    current: int = 0
    total: int = 0
    message: str = ""
    timestamp: datetime = datetime.now()
    elapsed_time: timedelta = timedelta()
    estimated_remaining: Optional[timedelta] = None
    speed: Optional[float] = None  # e.g., files/second, bytes/second
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def is_complete(self) -> bool:
        """Check if the operation is complete."""
        return self.state in (
            ProgressState.COMPLETED,
            ProgressState.CANCELLED,
            ProgressState.FAILED,
        )

    def is_active(self) -> bool:
        """Check if the operation is actively in progress."""
        return self.state == ProgressState.IN_PROGRESS

    def get_progress_ratio(self) -> float:
        """Get the progress ratio (0.0 to 1.0)."""
        return min(max(self.percentage / 100.0, 0.0), 1.0)


@dataclass
class OperationEvent:
    """
    Data class representing an operation event.

    Attributes:
        event_type: Type of event
        operation_type: Type of operation
        timestamp: When the event occurred
        data: Event-specific data
        source: Source of the event
    """

    event_type: str
    operation_type: OperationType
    timestamp: datetime = datetime.now()
    data: Optional[Dict[str, Any]] = None
    source: str = "unknown"

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class IProgressObserver(ABC):
    """
    Interface for progress observers.

    Observers implement this interface to receive progress updates
    and operation completion notifications.
    """

    @abstractmethod
    def on_progress_update(self, progress: ProgressInfo) -> None:
        """
        Called when progress is updated.

        Args:
            progress: Progress information
        """
        pass

    @abstractmethod
    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """
        Called when operation completes.

        Args:
            progress: Final progress information
            success: Whether the operation succeeded
        """
        pass

    @abstractmethod
    def on_cancellation(self, progress: ProgressInfo) -> None:
        """
        Called when operation is cancelled.

        Args:
            progress: Progress information at cancellation time
        """
        pass

    @abstractmethod
    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """
        Called when an error occurs during operation.

        Args:
            progress: Progress information at error time
            error: The exception that occurred
        """
        pass

    def on_event(self, event: OperationEvent) -> None:
        """
        Called when an operation event occurs.

        Args:
            event: Operation event information
        """
        # Optional method with default implementation
        pass


class ProgressSubject:
    """
    Subject that maintains a list of observers and notifies them of progress.

    This class implements the Subject role in the Observer pattern.
    """

    def __init__(self):
        """Initialize the progress subject with empty observer list."""
        self._observers: List[IProgressObserver] = []
        self._operation_start_time: Optional[datetime] = None
        self._last_progress: Optional[ProgressInfo] = None

    def attach(self, observer: IProgressObserver) -> None:
        """
        Attach an observer to this subject.

        Args:
            observer: The observer to attach

        Raises:
            ObserverRegistrationError: If observer is already attached
        """
        if observer in self._observers:
            raise ObserverRegistrationError(f"Observer {observer} is already attached")

        self._observers.append(observer)

    def detach(self, observer: IProgressObserver) -> None:
        """
        Detach an observer from this subject.

        Args:
            observer: The observer to detach
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def detach_all(self) -> None:
        """Detach all observers from this subject."""
        self._observers.clear()

    def get_observer_count(self) -> int:
        """
        Get the number of attached observers.

        Returns:
            Number of attached observers
        """
        return len(self._observers)

    def notify_progress(self, progress: ProgressInfo) -> None:
        """
        Notify all observers of a progress update.

        Args:
            progress: Progress information to notify

        Raises:
            ObserverNotificationError: If notification fails
        """
        self._last_progress = progress

        for observer in self._observers:
            try:
                observer.on_progress_update(progress)
            except Exception as e:
                # Continue notifying other observers even if one fails
                raise ObserverNotificationError(
                    f"Failed to notify observer {observer}: {str(e)}"
                ) from e

    def notify_completion(self, success: bool) -> None:
        """
        Notify all observers of operation completion.

        Args:
            success: Whether the operation succeeded

        Raises:
            ObserverNotificationError: If notification fails
        """
        if self._last_progress is None:
            # Create a minimal progress info if none exists
            progress = ProgressInfo(
                operation_type=OperationType.UNKNOWN,
                state=ProgressState.COMPLETED if success else ProgressState.FAILED,
                percentage=100.0 if success else 0.0,
            )
        else:
            # Update the state of the last progress
            progress_dict = self._last_progress.__dict__.copy()
            progress_dict["state"] = (
                ProgressState.COMPLETED if success else ProgressState.FAILED
            )
            progress_dict["percentage"] = (
                100.0 if success else self._last_progress.percentage
            )
            progress = ProgressInfo(**progress_dict)

        for observer in self._observers:
            try:
                observer.on_completion(progress, success)
            except Exception as e:
                raise ObserverNotificationError(
                    f"Failed to notify observer {observer}: {str(e)}"
                ) from e

    def notify_cancellation(self) -> None:
        """
        Notify all observers of operation cancellation.

        Raises:
            ObserverNotificationError: If notification fails
        """
        if self._last_progress is None:
            progress = ProgressInfo(
                operation_type=OperationType.UNKNOWN,
                state=ProgressState.CANCELLED,
                percentage=0.0,
            )
        else:
            # Create a copy of the last progress dict and update the state
            progress_dict = self._last_progress.__dict__.copy()
            progress_dict["state"] = ProgressState.CANCELLED
            progress = ProgressInfo(**progress_dict)

        for observer in self._observers:
            try:
                observer.on_cancellation(progress)
            except Exception as e:
                raise ObserverNotificationError(
                    f"Failed to notify observer {observer}: {str(e)}"
                ) from e

    def notify_error(self, error: Exception) -> None:
        """
        Notify all observers of an error.

        Args:
            error: The exception that occurred

        Raises:
            ObserverNotificationError: If notification fails
        """
        if self._last_progress is None:
            progress = ProgressInfo(
                operation_type=OperationType.UNKNOWN,
                state=ProgressState.FAILED,
                percentage=0.0,
                message=str(error),
            )
        else:
            progress_dict = self._last_progress.__dict__.copy()
            progress_dict["state"] = ProgressState.FAILED
            progress_dict["message"] = str(error)
            progress = ProgressInfo(**progress_dict)

        for observer in self._observers:
            try:
                observer.on_error(progress, error)
            except Exception as e:
                raise ObserverNotificationError(
                    f"Failed to notify observer {observer}: {str(e)}"
                ) from e

    def notify_event(self, event: OperationEvent) -> None:
        """
        Notify all observers of an event.

        Args:
            event: The operation event
        """
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception:
                # Continue with other observers even if one fails
                pass

    def start_operation(self, operation_type: OperationType) -> None:
        """
        Start tracking a new operation.

        Args:
            operation_type: Type of operation being started
        """
        self._operation_start_time = datetime.now()
        self._last_progress = None

        # Notify observers of operation start
        event = OperationEvent(
            event_type="operation_start",
            operation_type=operation_type,
            data={"timestamp": self._operation_start_time},
        )
        self.notify_event(event)

    def update_progress(
        self,
        operation_type: OperationType,
        percentage: float,
        current: int,
        total: int,
        message: str = "",
        state: ProgressState = ProgressState.IN_PROGRESS,
    ) -> ProgressInfo:
        """
        Update progress and notify observers.

        Args:
            operation_type: Type of operation
            percentage: Progress percentage
            current: Current progress value
            total: Total progress value
            message: Optional progress message
            state: Progress state

        Returns:
            The ProgressInfo object that was created
        """
        if self._operation_start_time is None:
            self._operation_start_time = datetime.now()

        elapsed_time = datetime.now() - self._operation_start_time

        # Calculate estimated remaining time if we have progress
        estimated_remaining = None
        if percentage > 0 and state == ProgressState.IN_PROGRESS:
            time_per_percent = elapsed_time / (percentage / 100.0)
            remaining_percent = 100.0 - percentage
            estimated_remaining = time_per_percent * (remaining_percent / 100.0)

        # Calculate speed if we have total
        speed = None
        if total > 0 and elapsed_time.total_seconds() > 0:
            speed = current / elapsed_time.total_seconds()

        progress = ProgressInfo(
            operation_type=operation_type,
            state=state,
            percentage=percentage,
            current=current,
            total=total,
            message=message,
            timestamp=datetime.now(),
            elapsed_time=elapsed_time,
            estimated_remaining=estimated_remaining,
            speed=speed,
        )

        self.notify_progress(progress)
        return progress

    def complete_operation(self, success: bool) -> None:
        """
        Complete the current operation and notify observers.

        Args:
            success: Whether the operation succeeded
        """
        self.notify_completion(success)
        self._operation_start_time = None

    def cancel_operation(self) -> None:
        """Cancel the current operation and notify observers."""
        self.notify_cancellation()
        self._operation_start_time = None

    def report_error(self, error: Exception) -> None:
        """
        Report an error and notify observers.

        Args:
            error: The exception that occurred
        """
        self.notify_error(error)
        self._operation_start_time = None


class CompositeProgressObserver(IProgressObserver):
    """
    Composite observer that delegates to multiple observers.

    Useful for combining multiple observers into a single observer.
    """

    def __init__(self):
        """Initialize with empty observer list."""
        self._observers: List[IProgressObserver] = []

    def add_observer(self, observer: IProgressObserver) -> None:
        """
        Add an observer to the composite.

        Args:
            observer: Observer to add
        """
        self._observers.append(observer)

    def remove_observer(self, observer: IProgressObserver) -> None:
        """
        Remove an observer from the composite.

        Args:
            observer: Observer to remove
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def on_progress_update(self, progress: ProgressInfo) -> None:
        """Notify all observers of progress update."""
        for observer in self._observers:
            observer.on_progress_update(progress)

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """Notify all observers of completion."""
        for observer in self._observers:
            observer.on_completion(progress, success)

    def on_cancellation(self, progress: ProgressInfo) -> None:
        """Notify all observers of cancellation."""
        for observer in self._observers:
            observer.on_cancellation(progress)

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """Notify all observers of error."""
        for observer in self._observers:
            observer.on_error(progress, error)

    def on_event(self, event: OperationEvent) -> None:
        """Notify all observers of event."""
        for observer in self._observers:
            observer.on_event(event)


class FilteringProgressObserver(IProgressObserver):
    """
    Observer that filters progress updates based on criteria.

    Useful for reducing the frequency of notifications.
    """

    def __init__(
        self,
        delegate: IProgressObserver,
        min_percentage_change: float = 1.0,
        min_time_interval: float = 0.1,
    ):
        """
        Initialize the filtering observer.

        Args:
            delegate: The observer to delegate to
            min_percentage_change: Minimum percentage change to notify (default: 1.0%)
            min_time_interval: Minimum time between notifications in seconds (default: 0.1s)
        """
        self._delegate = delegate
        self._min_percentage_change = min_percentage_change
        self._min_time_interval = min_time_interval
        self._last_percentage = 0.0
        self._last_notification_time = datetime.min

    def on_progress_update(self, progress: ProgressInfo) -> None:
        """Filter progress updates before notifying delegate."""
        now = datetime.now()
        time_since_last = (now - self._last_notification_time).total_seconds()

        percentage_change = abs(progress.percentage - self._last_percentage)

        if (
            percentage_change >= self._min_percentage_change
            and time_since_last >= self._min_time_interval
        ):
            self._delegate.on_progress_update(progress)
            self._last_percentage = progress.percentage
            self._last_notification_time = now

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """Always notify delegate of completion."""
        self._delegate.on_completion(progress, success)

    def on_cancellation(self, progress: ProgressInfo) -> None:
        """Always notify delegate of cancellation."""
        self._delegate.on_cancellation(progress)

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """Always notify delegate of errors."""
        self._delegate.on_error(progress, error)

    def on_event(self, event: OperationEvent) -> None:
        """Always notify delegate of events."""
        self._delegate.on_event(event)


class ProgressObserverAdapter:
    """
    Adapter to convert between different progress observer interfaces.

    Useful for integrating with external systems that have different
    progress reporting interfaces.
    """

    def __init__(self, adapter_func: Callable[[ProgressInfo], Any]):
        """
        Initialize the adapter.

        Args:
            adapter_func: Function to adapt ProgressInfo to target format
        """
        self._adapter_func = adapter_func
        self._observers: List[Callable[[Any], None]] = []

    def add_target_observer(self, observer: Callable[[Any], None]) -> None:
        """
        Add an observer that expects the target format.

        Args:
            observer: Observer function expecting adapted format
        """
        self._observers.append(observer)

    def on_progress_update(self, progress: ProgressInfo) -> None:
        """Adapt progress update and notify target observers."""
        adapted = self._adapter_func(progress)
        for observer in self._observers:
            observer(adapted)

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """Adapt completion and notify target observers."""
        adapted = self._adapter_func(progress)
        for observer in self._observers:
            observer({"progress": adapted, "success": success})

    def on_cancellation(self, progress: ProgressInfo) -> None:
        """Adapt cancellation and notify target observers."""
        adapted = self._adapter_func(progress)
        for observer in self._observers:
            observer({"progress": adapted, "cancelled": True})

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """Adapt error and notify target observers."""
        adapted = self._adapter_func(progress)
        for observer in self._observers:
            observer({"progress": adapted, "error": str(error)})


class NullProgressObserver(IProgressObserver):
    """
    Null observer that does nothing.

    Useful as a default observer or for testing.
    """

    def on_progress_update(self, progress: ProgressInfo) -> None:
        """Do nothing."""
        pass

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """Do nothing."""
        pass

    def on_cancellation(self, progress: ProgressInfo) -> None:
        """Do nothing."""
        pass

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """Do nothing."""
        pass


class EventDispatcher:
    """
    Dispatcher for operation events.

    Provides a more flexible event system that can be used alongside
    the observer pattern.
    """

    def __init__(self):
        """Initialize the event dispatcher."""
        self._listeners: Dict[str, List[Callable[[OperationEvent], None]]] = {}

    def add_listener(
        self, event_type: str, listener: Callable[[OperationEvent], None]
    ) -> None:
        """
        Add a listener for a specific event type.

        Args:
            event_type: Type of event to listen for
            listener: Function to call when event occurs
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def remove_listener(
        self, event_type: str, listener: Callable[[OperationEvent], None]
    ) -> None:
        """
        Remove a listener for a specific event type.

        Args:
            event_type: Type of event
            listener: Function to remove
        """
        if event_type in self._listeners:
            if listener in self._listeners[event_type]:
                self._listeners[event_type].remove(listener)

    def dispatch(self, event: OperationEvent) -> None:
        """
        Dispatch an event to all listeners.

        Args:
            event: The event to dispatch
        """
        # Notify specific listeners for this event type
        if event.event_type in self._listeners:
            for listener in self._listeners[event.event_type]:
                try:
                    listener(event)
                except Exception:
                    # Continue with other listeners even if one fails
                    pass

        # Notify wildcard listeners
        if "*" in self._listeners:
            for listener in self._listeners["*"]:
                try:
                    listener(event)
                except Exception:
                    pass

    def clear(self) -> None:
        """Clear all listeners."""
        self._listeners.clear()
