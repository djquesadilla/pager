import threading
import time

class TimeManager:
    def __init__(self, pager_service):
        self.pager_service = pager_service
        self.timers = {}

    def set_timer(self, alert):
        print("TIMEOUT SET")
        timer = threading.Timer(2, self.handle_timeout)
        self.timers[alert] = timer
        timer.start()

    def cancel_timer(self, alert):
        if alert in self.timers:
            self.timers[alert].cancel()
            del self.timers[alert]
    
    def handle_timeout(self):
        print("Timeout for alert")
        self.cancel_timer("alert")

    def __str__(self):
        return f"Timers: {self.timers}"

time_manager = TimeManager("pager_service")
time_manager.set_timer("alert")
print(time_manager)
time.sleep(5)
print(time_manager)

