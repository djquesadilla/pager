class EventEmitter:
    def __init__(self):
        self._listeners = {}

    def on(self, event_type, listener):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def emit(self, event_type, event):
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                listener(event)