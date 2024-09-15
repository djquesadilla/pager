import unittest
import datetime

from models import SMS, Alert, Email, EscalationPolicy, EscalationPolicyLevel, EscalationPolicyMonitoredService, PagerService, MonitoredService

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
      self.assertTrue(alert.acknowledged)

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
        """
        Use case #1:
        Given a Monitored Service in a Healthy State,
        when the Pager receives an Alert related to this Monitored Service,
        then the Monitored Service becomes Unhealthy,
        the Pager notifies all targets of the first level of the escalation policy,
        and sets a 15-minutes acknowledgement delay.
        """
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
        timeout = 1
        pager_service.receive_alert(alert, timeout)
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
        # Test that the timer acknowledgment delay was set to TIMEOUT seconds
        # the default in the app is 15 minutes
        timer = pager_service.timer_manager.timers[alert]
        self.assertIsNotNone(timer)
        self.assertEqual(timer.interval, timeout)
  
    def testHandleAcknowledgementTimeout(self):
        """
        Use case #2:
        Given an Alert that has not been acknowledged,
        when the acknowledgement delay expires,
        then the Alert escalates to the next level of the escalation policy,
        and notifies all targets of the new level.
        """
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
        # Start of Selection
        pager_service = PagerService(escalation_policy)
        pager_service.receive_alert(alert, 1)
        # Manually handle the acknowledgement timeout
        pager_service.handle_acknowledgement_timeout(alert)
        # Cancel the timer to prevent it from firing again and causing an exception
        pager_service.timer_manager.cancel_timer(alert)
        self.assertEqual(alert.current_level, 1)
        # Test that the alert was sent to all targets of the next level
        # Expected message for Email target in the second level:
        expected_message_level_0 = "Sending SMS to 900100200: service #1 is unhealthy (Level 0)"
        expected_message_level_1 = "Emailing user@example.com: service #1 is unhealthy (Level 1)"
        self.assertEqual(
          pager_service.alerts_log,
          [expected_message_level_0, expected_message_level_1]
        )
    
    def testHandleNoMoreEscalationLevelsException(self):
        service = MonitoredService('service #1')
        alert = Alert(service)
        escalation_policy = EscalationPolicy(
          {
            service.service_name: EscalationPolicyMonitoredService(
              service,
              [
                EscalationPolicyLevel([SMS('900100200')]),
              ]
            )
          }
        )
        pager_service = PagerService(escalation_policy)
        timeout = 2
        pager_service.receive_alert(alert, timeout)
        with self.assertRaises(Exception) as context:
            pager_service.handle_acknowledgement_timeout(alert)
            self.assertEqual(str(context.exception), 'No more escalation levels')
        
        pager_service.timer_manager.cancel_timer(alert)
    
    def testHandleAcknowledgement(self):
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
        timeout = 2
        pager_service.receive_alert(alert, timeout)

        pager_service.handle_acknowledgement(alert)
        self.assertTrue(alert.acknowledged)
        self.assertNotIn(alert, pager_service.alerts)
        self.assertNotIn(alert, pager_service.timer_manager.timers)
    

    def testHandleTimeoutAfterAcknowledgement(self):
        """
        User case #3:
        Given a Monitored Service in an Unhealthy State
        when the Pager receives the Acknowledgement
        and later receives the Acknowledgement Timeout,
        then the Pager doesn't notify any Target
        and doesn't set an acknowledgement delay.
        """
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
        timeout = 2
        pager_service.receive_alert(alert, timeout)
        pager_service.handle_acknowledgement(alert)

        with self.assertRaises(Exception) as context:
            pager_service.handle_acknowledgement_timeout(alert)
            self.assertEqual(str(context.exception), 'Alert already acknowledged')
    
    
        

if __name__ == '__main__':
    unittest.main()