import unittest
import datetime

from models import SMS, Alert, Email, EscalationPolicy, EscalationPolicyLevel, EscalationPolicyMonitoredService, PagerService, MonitoredService, Timer

class TestEmail(unittest.TestCase):
    def test_initialization(self):
        email = Email('user@example.com')
        self.assertEqual(email.email_address, 'user@example.com')
    
    def testNotify(self):
        email = Email('user@example.com')
        message = 'Service is down'
        self.assertEqual(
          email.notify(message),
          f'Emailing {email.email_address}: {message}'
        )

class TestSMS(unittest.TestCase):
    def test_initialization(self):
        sms = SMS('900100100')
        self.assertEqual(sms.phone_number, '900100100')

    def test_initialization(self):
        sms = SMS('900100100')
        message = 'Service is down'
        self.assertEqual(
          sms.notify(message),
          f'Sending SMS to {sms.phone_number}: {message}'
        )

class TestMonitoredService(unittest.TestCase):
    def test_initialization(self):
        service_name = 'service #1'
        service = MonitoredService(service_name)
        self.assertEqual(service.service_name, service_name)
        self.assertTrue(service.healthy)
    
    def testSetUnhealthy(self):
        service = MonitoredService('service #1')
        service.set_unhealthy()
        self.assertFalse(service.healthy)

    def testSetHealthy(self):
        service = MonitoredService('service #1')
        service.set_unhealthy()
        self.assertFalse(service.healthy)
        service.set_healthy()
        self.assertTrue(service.healthy)

class TestEscalationPolicyLevel(unittest.TestCase):
    def test_initialization(self):
        targets = [SMS('900100200'), Email('user@example.com')]
        escalation_policy_level = EscalationPolicyLevel(targets)
        self.assertEqual(escalation_policy_level.targets, targets)

class TestEscalationPolicyMonitoredService(unittest.TestCase):
    def test_initialization(self):
        monitored_service = MonitoredService('service #1')
        levels = [
          EscalationPolicyLevel([SMS('900100200')]),
          EscalationPolicyLevel([Email('user@example.com')])
        ]
        escalation_policy_monitored_service = EscalationPolicyMonitoredService(monitored_service, levels)
        self.assertEqual(escalation_policy_monitored_service.monitored_service, monitored_service)
        self.assertEqual(escalation_policy_monitored_service.levels, levels)

class TestEscalationPolicy(unittest.TestCase):
  def test_initialization(self):
      monitored_service = MonitoredService('service #1')
      levels = [
        EscalationPolicyLevel([SMS('900100200')]),
        EscalationPolicyLevel([Email('user@example.com')])
      ]
      escalation_policy_monitored_service = EscalationPolicyMonitoredService(monitored_service, levels)
      escalation_policy = EscalationPolicy(
        {
          monitored_service.service_name: escalation_policy_monitored_service
        }
      )
      self.assertEqual(
         escalation_policy.policies[monitored_service.service_name],
         escalation_policy_monitored_service
      )

class TestTimer(unittest.TestCase):
  def test_initialization(self):
      created_at = datetime.datetime.now()
      timer = Timer(created_at)
      self.assertEqual(timer.created_at, created_at)
      self.assertEqual(timer.timeout, created_at + datetime.timedelta(minutes=15))
      self.assertFalse(timer.acknowledged)
  
  def testAcknowledge(self):
      timer = Timer(datetime.datetime.now())
      timer.acknowledge()
      self.assertTrue(timer.acknowledged)
      self.assertIsNone(timer.timeout)

class TestAlert(unittest.TestCase):
  def test_initialization(self):
      service = MonitoredService('service #1')
      alert = Alert(service)
      self.assertEqual(alert.monitored_service, service)
      self.assertEqual(alert.current_level, 0)
      self.assertEqual(alert.message, f'{service.service_name} is unhealthy (Level {alert.current_level})')
  
  def testEscalate(self):
      service = MonitoredService('service #1')
      alert = Alert(service)
      alert.escalate()
      self.assertEqual(alert.current_level, 1)
  
  def testAcknowledge(self):
      service = MonitoredService('service #1')
      alert = Alert(service)
      alert.acknowledge()
      self.assertTrue(alert.timer.acknowledged)
      self.assertIsNone(alert.timer.timeout)

class TestPagerService(unittest.TestCase):
    def test_initialization(self):
      service = MonitoredService('service #1')
      pager_service = PagerService(EscalationPolicy(
        {
          service.service_name: EscalationPolicyMonitoredService(
            service,
            [
              EscalationPolicyLevel([SMS('900100200')]),
              EscalationPolicyLevel([Email('user@example.com')])
            ]
          )
        }
      ))
      self.assertIsInstance(pager_service.alerts, list)
  
    def testReceiveAlert(self):
        # Use case #1:
        # Given a Monitored Service in a Healthy State,
        # when the Pager receives an Alert related to this Monitored Service,
        # then the Monitored Service becomes Unhealthy,
        # the Pager notifies all targets of the first level of the escalation policy,
        # and sets a 15-minutes acknowledgement delay.
        service= MonitoredService('service #1')
        alert = Alert(service)
        escalation_policy = EscalationPolicy(
          {
            service.service_name: EscalationPolicyMonitoredService(
              service,
              [
                EscalationPolicyLevel([SMS('900100200')]),
                EscalationPolicyLevel([Email('user@example.com')])
              ]
            )
          }
        )
        pager_service = PagerService(escalation_policy)
        pager_service.receive_alert(alert)
        self.assertIn(alert, pager_service.alerts)
        self.assertFalse(service.healthy)
        # Test that the alert was sent to all targets of the escalation policy
        # Expected message for SMS target in the first level:
        expected_message = "Sending SMS to 900100200: service #1 is unhealthy (Level 0)"
        self.assertEqual(
          pager_service.alerts_log,
          [expected_message]
        )
        self.assertCountEqual(
          pager_service.alerts_log,
          [expected_message]
        )
        # test that the timer acknowledgment delay was set to 15 minutes
        self.assertEqual(alert.timer.timeout, alert.timer.created_at + datetime.timedelta(minutes=15))
  
    def testHandleAcknowledgementTimeout(self):
        # Use case #2:
        # Given an Alert that has not been acknowledged,
        # when the acknowledgement delay expires,
        # then the Alert escalates to the next level of the escalation policy,
        # and notifies all targets of the new level.
        service = MonitoredService('service #1')
        alert = Alert(service)
        escalation_policy = EscalationPolicy(
          {
            service.service_name: EscalationPolicyMonitoredService(
              service,
              [
                EscalationPolicyLevel([SMS('900100200')]),
                EscalationPolicyLevel([Email('user@example.com')])
              ]
            )
          }
        )
        pager_service = PagerService(escalation_policy)
        pager_service.receive_alert(alert)
        pager_service.handle_acknowledgement_timeout(alert)
        self.assertEqual(alert.current_level, 1)
        # Test that the alert was sent to all targets of the next level
        # Expected message for Email target in the second level:
        expected_message_level_0 = "Sending SMS to 900100200: service #1 is unhealthy (Level 0)"
        expected_message_level_1 = "Emailing user@example.com: service #1 is unhealthy (Level 1)"
        self.assertEqual(
          pager_service.alerts_log,
          [expected_message_level_0, expected_message_level_1]
        )


if __name__ == '__main__':
    unittest.main()