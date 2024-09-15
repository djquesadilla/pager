import datetime
from typing import List, Optional


from abc import ABC, abstractmethod

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

class Timer:
    def __init__(self, created_at: datetime.datetime):
        self.created_at: datetime.datetime = created_at
        self.timeout: Optional[datetime.datetime] = self.created_at + datetime.timedelta(minutes=15)
        self.acknowledged: bool = False
    
    def acknowledge(self):
        self.acknowledged = True
        self.timeout = None

class Alert:
    def __init__(self, monitored_service):
        self.monitored_service: MonitoredService = monitored_service
        self.sent_at: datetime.datetime = datetime.datetime.now()
        self.current_level: int = 0
        self.timer = Timer(self.sent_at)
    
    def escalate(self):
        self.current_level += 1

    def acknowledge(self):
        self.timer.acknowledge()
    
    @property
    def message(self) -> str:
        return f'{self.monitored_service.service_name} is unhealthy (Level {self.current_level})'
    
    def __str__(self):
        return (
            f"Alert for {self.monitored_service.service_name}\n"
            f"Sent at {self.sent_at}\n"
            f"Current escalation level: {self.current_level}\n"
            f"Timeout for acknowledge: {self.timer.timeout}\n"
            f"Acknowledged: {self.timer.acknowledged}"
        )

class PagerService:
    def __init__(self, escalation_policy: EscalationPolicy):
        self.escalation_policy: EscalationPolicy = escalation_policy
        self.alerts: List[Alert] = []
        self.alerts_log = [] # log 
    
    def receive_alert(self, alert: Alert):
        # append the alert to the list of alerts
        self.alerts.append(alert)
        # set the service to unhealthy
        alert.monitored_service.set_unhealthy()
        # send the alert to all targets of the escalation policy current level
        self._send_to_targets(alert)
        # sets timer acknowledgment delay to 15 minutes
    
    def handle_acknowledgement_timeout(self, alert: Alert):
        if not alert.timer.acknowledged:
            alert.escalate()
            self._send_to_targets(alert)
    
    def _send_to_targets(self, alert: Alert):
        targets = self.escalation_policy.policies[alert.monitored_service.service_name].levels[alert.current_level].targets
        for target in targets:
            self.alerts_log.append(target.notify(alert.message))