import datetime
import threading
from typing import List, Optional


from abc import ABC, abstractmethod

from event_emitter import EventEmitter

class Target(ABC):
    @abstractmethod
    def notify(self, message: str):
      pass

class Email(Target):
    def __init__(self, email_address):
        self.email_address = email_address
    
    def notify(self, message: str) -> str:
        res = f'Emailing {self.email_address}: {message}'
        # TODO: send email adapter here
        return res
    
class SMS(Target):
    def __init__(self, phone_number):
        self.phone_number = phone_number
    
    def notify(self, message: str) -> str:
        res = f'Sending SMS to {self.phone_number}: {message}'
        # TODO: send sms adapter here
        return res

class MonitoredService:
    def __init__(self, service_name):
        self.service_name = service_name
        self.healthy = True
    
    def set_unhealthy(self):
        self.healthy = False
    
    def set_healthy(self):
        self.healthy = True

class EscalationPolicyLevel:
    def __init__(self, targets: List[Target]):
        self.targets = targets
    
class EscalationPolicyMonitoredService:
    def __init__(self, monitored_service: MonitoredService, levels: List[EscalationPolicyLevel]):
        self.monitored_service = monitored_service
        self.levels: List[EscalationPolicyLevel] = levels

    def level_targets(self, level: int) -> List[Target]:
        return self.levels[level].targets

class EscalationPolicy:
    def __init__(self, policies: dict):
        self.policies: dict = policies # Dictionary with monitored_service name as keys and EscalationPolicyMonitoredService as values
    
    def __str__(self):
        return f"{self.policies}"

class Alert:
    def __init__(self, monitored_service):
        self.monitored_service: MonitoredService = monitored_service
        self.sent_at: datetime.datetime = datetime.datetime.now()
        self.current_level: int = 0
        self.acknowledged: bool = False
    
    def escalate(self):
        self.current_level += 1

    def acknowledge(self):
        self.acknowledged = True
    
    @property
    def message(self) -> str:
        return f'{self.monitored_service.service_name} is unhealthy (Level {self.current_level})'
    
    def __str__(self):
        return (
            f"Alert for {self.monitored_service.service_name}\n"
            f"Sent at {self.sent_at}\n"
            f"Current escalation level: {self.current_level}\n"
            f"Timeout for acknowledge: {self.timer.timeout}\n"
        )

class TimeoutEvent:
    alert: Alert

    def __init__(self, alert: Alert):
        self.alert = alert

class TimerManager:
    def __init__(self, event_emitter: EventEmitter):
        self.event_emitter: EventEmitter = event_emitter
        self.timers = {} # Dictionary with alert as key and timer as value
    
    def set_timer(self, alert, seconds: Optional[int] = None):
        timeout: datetime.datetime = seconds if seconds else datetime.timedelta(minutes=15).total_seconds()
        timer: threading.Timer = threading.Timer(timeout, self._handle_timeout, args=[alert])
        self.timers[alert] = timer
        timer.start()
    
    def cancel_timer(self, alert):
        if alert in self.timers:
            self.timers[alert].cancel()
            del self.timers[alert]
    
    def _handle_timeout(self, alert: Alert):
        self.event_emitter.emit('timeout', TimeoutEvent(alert))
    
    def __str__(self):
        return f"Timers: {self.timers}"

class PagerService:
    def __init__(self, escalation_policy: EscalationPolicy):
        self.escalation_policy: EscalationPolicy = escalation_policy
        self.alerts: dict = {} # { MonitoredService: Alert } 
        self.alerts_log = [] # log

        self.event_emitter = EventEmitter()
        self.timer_manager = TimerManager(self.event_emitter)

        # subscribe to timeout event
        self.event_emitter.on('timeout', self._handle_timeout_event)
    
    def receive_alert(self, alert: Alert, seconds: Optional[int] = None):
        if alert.monitored_service not in self.alerts:
          # append the alert to the list of alerts
          self.alerts[alert.monitored_service] = alert
          # set the service to unhealthy
          alert.monitored_service.set_unhealthy()
          # send the alert to all targets of the escalation policy current level
          self._send_to_targets(alert)
          # sets timer acknowledgment delay to 15 minutes
          self.timer_manager.set_timer(alert, seconds)
        else:
          raise Exception('Alert already exists')
    
    def _handle_timeout_event(self, event: TimeoutEvent):
        self.handle_acknowledgement_timeout(event.alert)

    def handle_acknowledgement_timeout(self, alert: Alert):
        if not alert.acknowledged:
            alert.escalate()
            if alert.current_level < self._escalation_levels_count(alert):
                self._send_to_targets(alert)
            else:
                self.timer_manager.cancel_timer(alert)
                # TODO: future work, this is the extreme case, we should notify the service owner
                raise Exception('No more escalation levels')
        else:
            self.alerts.remove(alert)
            self.timer_manager.cancel_timer(alert)
            raise Exception('Alert already acknowledged')
    
    def handle_acknowledgement(self, alert: Alert):
        alert.acknowledge()
        self.timer_manager.cancel_timer(alert)
        del self.alerts[alert.monitored_service]
    
    def _send_to_targets(self, alert: Alert):
        if alert.monitored_service.healthy:
            self.timer_manager.cancel_timer(alert)
            del self.alerts[alert.monitored_service]
            raise Exception('Service is healthy')
        else:
            targets = self.escalation_policy.policies[alert.monitored_service.service_name].levels[alert.current_level].targets
            for target in targets:
                self.alerts_log.append(target.notify(alert.message))
    
    def _escalation_levels_count(self, alert: Alert) -> int:
        return len(self.escalation_policy.policies[alert.monitored_service.service_name].levels)
    
    def __str__(self):
        return (
            f"Alerts: {self.alerts}\n"
            f"Alerts log: {self.alerts_log}\n"
            f"Escalation policy: {self.escalation_policy}\n"
            f"Timer manager: {self.timer_manager}"
        )