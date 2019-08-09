from time import sleep, time
import json
from sys import exit
import logging
import RPi.GPIO as gpio
import devices

class Test():
    """Used for testing of functionality of PIRA"""

    def __init__(self, boot, test_data_index, test_routine, num_rep):

        self.current_state = ""
        self.power_pin = False
        self.boot = boot
        self.test_data_index = test_data_index
        self.test_routine = test_routine
        self.num_rep = num_rep
        self.set_status_pin_low()

        self.boot.print_and_log('====================TEST PARAMETERS====================')
        self.boot.print_and_log('Test started with paramters:')
        self.boot.print_and_log('- test_data_index: ' + str(test_data_index))
        self.boot.print_and_log('- test_routine: ' + str(test_routine))
        self.boot.print_and_log('- num_rep: ' + str(num_rep))

        self.test_data = self.prepare_test_data(test_data_index)

        self.start_test()

    def read_json_file(self):
        """Functions reads data from json file and returns its content"""

        try:
            with open('values.json') as f:
              data = json.load(f)
        except Exception:
            self.boot.print_and_log('File found:                                      NOT OK')
            exit("CAN NOT FIND JSON FILE, PROGRAM STOPPED!")
        else:
            #self.boot.print_and_log('File found:                                          OK')
            return data

    def prepare_test_data(self, test_data_index):
        """Function prepares json data for testing framework"""
        data = self.read_json_file()

        test_data  = [0 for x in range(4)] # prepare empty list with 4 elements

        test_data[0] = data['values'][test_data_index]["pira_on_time"]
        test_data[1] = data['values'][test_data_index]["pira_off_time"]
        test_data[2] = data['values'][test_data_index]["pira_reboot_time"]
        test_data[3] = data['values'][test_data_index]["pira_wakeup_time"]

        return test_data

    def send_test_data(self):
        """Sends test data over uart to pira"""

        self.boot.print_and_log("Sending new test data:                               OK")

        self.boot.pirasmart.set_on_time(self.test_data[0])
        self.boot.pirasmart.set_off_time(self.test_data[1])
        self.boot.pirasmart.set_reboot_time(self.test_data[2])
        self.boot.pirasmart.set_wakeup_time(self.test_data[3])

    def verify_sent_data(self):
        """Checks returned values to see if they match with the ones sent"""

        pira_ok = self.boot.pirasmart.read()
        if self.test_data[0] == self.boot.get_pira_on_timer() and \
        self.test_data[1] == self.boot.get_pira_sleep_timer() and \
        self.test_data[2] == self.boot.get_pira_reboot_timer() and \
        self.test_data[3] == self.boot.get_pira_wakeup_timer():
            self.boot.print_and_log("Sent data verified:                                  OK")
            self.boot.print_and_log('-------------------------------------------------------')
            return True
        else:
            self.boot.print_and_log("Sent data verified:                              NOT OK")
            self.boot.print_and_log('Failed to verify data!')
            self.boot.print_and_log('On time is ' + str(self.boot.get_pira_on_timer()) + " should be " + str(self.test_data[0]))
            self.boot.print_and_log('Sleep timer is ' + str(self.boot.get_pira_sleep_timer()) + " should be " + str(self.test_data[1]))
            self.boot.print_and_log('Reboot timer is ' + str(self.boot.get_pira_reboot_timer()) + " should be " + str(self.test_data[2]))
            self.boot.print_and_log('Wakeup timer is ' + str(self.boot.get_pira_wakeup_timer()) + " should be " + str(self.test_data[3]))
            self.boot.print_and_log('-------------------------------------------------------')
            return False

    def send_and_verify_data(self):
        """
        Function sends test data and verifies it, if
        fails it tries to do this 4 more times if unsuccesful returns false.
        """
        timeout = 0
        while True:
            # First send and verify data
            self.send_test_data()
            if self.verify_sent_data():
                return True
            else:
                timeout += 1
                if timeout >= 5:
                    self.boot.print_and_log('Failed to verify data 5 times, exit program')
                    return False
                sleep(1)

    def read_power_pin(self):
        """Returns state of power pin"""
        return gpio.input(devices.GPIO_POWER_SUPPLY_PIN)

    def set_status_pin_high(self):
        """Sets status pin high"""
        gpio.output(devices.GPIO_PIRA_STATUS_PIN, gpio.HIGH)

    def set_status_pin_low(self):
        """Sets status pin low"""
        gpio.output(devices.GPIO_PIRA_STATUS_PIN, gpio.LOW)

    def wait_for_wait_status_on_state(self):
        """
        Function will block code, until we are in WAIT_STATUS_ON_STATE,
        which is a common starting ponit for all test routines.
        """
        self.boot.print_and_log("Waiting for common start point")
        while True:
            pira_ok = self.boot.pirasmart.read()
            self.current_state = self.boot.get_pira_state()
            if self.current_state == "WAIT_STATUS_ON":
                self.boot.print_and_log("Common start point found")
                break
        self.boot.print_and_log('-------------------------------------------------------')

    def update_state_and_pin_values(self):
        """Needed to update current state of pira and to update power pin value"""
        self.boot.pirasmart.read()
        self.power_pin = self.read_power_pin()
        self.current_state = self.boot.get_pira_state()

    def log_mistake(self, correct_state, correct_power_pin):
        """Function logs information about current state and power variable into log file"""

        self.boot.print_and_log("Incorrect state or power pin value!")
        self.boot.print_and_log("Correct state: " + correct_state)
        self.boot.print_and_log("Current state: " + self.current_state)
        self.boot.print_and_log("Correct power pin value: " + str(correct_power_pin))
        self.boot.print_and_log("Current power pin value: " + str(self.power_pin))

    def wait_for_next_state(self, current_state, expected_state):
        """
        Function is checking the state and power pin, it will block until
        correct ones are received or timeout is reached.
        Expected_state should be a string, expected_power pin should be a 0 or 1.
        """
        if current_state == "WAIT_STATUS_ON" or current_state == "WAKEUP":
            i = 0
        elif current_state == "IDLE":
            if self.test_data[1] < self.test_data[3]:
                i = 1
            else:
                i = 3
        elif current_state == "REBOOT_DETECTION":
            i = 2
        else:
            exit("Wrong state")

        if expected_state == "IDLE":
            expected_power_pin = 0
        else:
            expected_power_pin = 1

        start_time = time()
        while True:
            self.update_state_and_pin_values()
            if self.current_state == expected_state and self.power_pin == expected_power_pin:
                return True

            if (time() - start_time) >= self.test_data[i]:
                self.log_mistake(expected_state, expected_power_pin)
                return False

    def wait_idle_routine(self):
        """
        Function is checking if PIRA transitions from WAIT_STATUS_ON to
                                                      IDLE to
                                                      WAIT_STATUS_ON state.
        """
        self.boot.print_and_log("WAIT, IDLE routine started!")


        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, IDLE routine finished:                     NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="IDLE"):
            self.boot.print_and_log("WAIT, IDLE routine finished:                     NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: IDLE")

        if not self.wait_for_next_state(current_state="IDLE", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, IDLE routine finished:                     NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.boot.print_and_log("WAIT, IDLE routine finished:                         OK")
        self.boot.print_and_log('-------------------------------------------------------')
        return True

    def wait_wake_reboot_idle_routine(self):
        """
        Function is checking if PIRA transitions from WAIT_STATUS_ON to
                                                      WAKEUP to
                                                      REBOOT DETECTION to
                                                      IDLE state.
        """
        self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine started!")


        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:       NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAKEUP"):
            self.boot.print_and_log("failed 1")
            self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:       NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="REBOOT_DETECTION"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:       NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: REBOOT_DETECTION")

        if not self.wait_for_next_state(current_state="REBOOT_DETECTION", expected_state="IDLE"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:       NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: IDLE")

        if not self.wait_for_next_state(current_state="IDLE", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:       NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.boot.print_and_log("WAIT, WAKE, REBOOT, IDLE routine finished:           OK")
        self.boot.print_and_log('-------------------------------------------------------')
        return True

    def wait_wake_idle_routine(self):
        """
        Function is checking if PIRA transitions from WAIT_STATUS_ON to
                                                      WAKEUP to
                                                      IDLE state.
        """
        self.boot.print_and_log("WAIT, WAKE, IDLE routine started!")

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, IDLE routine finished:               NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAKEUP"):
            self.boot.print_and_log("WAIT, WAKE, IDLE routine finished:               NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="IDLE"):
            self.boot.print_and_log("WAIT, WAKE, IDLE routine finished:               NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: IDLE")

        # Turn off status pin, to mimic behavior off turned off raspi
        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="IDLE", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, IDLE routine finished:               NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.boot.print_and_log("WAIT, WAKE, IDLE routine finished:                   OK")
        self.boot.print_and_log('-------------------------------------------------------')
        return True

    def wait_wake_reboot_wake_idle_routine(self):
        """
        Function is checking if PIRA transitions from WAIT_STATUS_ON to
                                                      WAKEUP to
                                                      REBOOT DETECTION to
                                                      WAKEUP to
                                                      IDLE state.
        """
        self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine started!")


        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAKEUP"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="REBOOT_DETECTION"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: REBOOT_DETECTION")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="REBOOT_DETECTION", expected_state="WAKEUP"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="IDLE"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: IDLE")

        # Turn off status pin, to mimic behavior of turned off raspi
        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="IDLE", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished: NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, IDLE routine finished:     OK")
        self.boot.print_and_log('-------------------------------------------------------')
        return True

    def wait_wake_reboot_wake_reboot_idle_routine(self):
        """
        Function is checking if PIRA transitions from WAIT_STATUS_ON to
                                                      WAKEUP to
                                                      REBOOT DETECTION to
                                                      WAKEUP to
                                                      REBOOT DETECTION to
                                                      IDLE state.
        """
        self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine started!")

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="WAIT_STATUS_ON", expected_state="WAKEUP"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="REBOOT_DETECTION"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: REBOOT_DETECTION")

        self.set_status_pin_high()

        if not self.wait_for_next_state(current_state="REBOOT_DETECTION", expected_state="WAKEUP"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAKEUP")

        self.set_status_pin_low()

        if not self.wait_for_next_state(current_state="WAKEUP", expected_state="REBOOT_DETECTION"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: REBOOT_DETECTION")

        if not self.wait_for_next_state(current_state="REBOOT_DETECTION", expected_state="IDLE"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: IDLE")

        if not self.wait_for_next_state(current_state="IDLE", expected_state="WAIT_STATUS_ON"):
            self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
            self.boot.print_and_log("                                                 NOT OK")
            return False
        else:
            self.boot.print_and_log("Current state: WAIT_STATUS_ON")

        self.boot.print_and_log("WAIT, WAKE, REBOOT, WAKE, REBOOT, IDLE routine finished")
        self.boot.print_and_log("                                                     OK")
        self.boot.print_and_log('-------------------------------------------------------')
        return True

    def execute_routine(self, test_routine):
        if test_routine == 0:
            if self.wait_idle_routine():
                return True
        elif test_routine == 1:
            if self.wait_wake_reboot_idle_routine():
                return True
        elif test_routine == 2:
            if self.wait_wake_idle_routine():
                return True
        elif test_routine == 3:
            if self.wait_wake_reboot_wake_idle_routine():
                return True
        elif test_routine == 4:
            if self.wait_wake_reboot_wake_reboot_idle_routine():
                return True
        else:
            self.boot.print_and_log("Incorrect test routine number!")
            exit()

        return False

    def start_test(self):
        """Main function that deals with test routines"""

        repetition = 0
        succesful = 0

        self.boot.print_and_log('=====================TEST ROUTINE======================')
        while True:
            if repetition >= self.num_rep:
                # Number of repetations reached 
                break

            # Start at known state
            self.wait_for_wait_status_on_state()

            # Send test data only at start or when reset happnes
            if repetition == 0 or self.boot.reset_flag:
                self.boot.reset_flag = False
                if not self.send_and_verify_data():
                    #Failed to verify data, no sense to continue testing this routine
                    self.boot.print_and_log('TEST ROUTINE FINISHED                            NOT OK')
                    return False

            #if ok start monitoring picked test routine
            if self.execute_routine(self.test_routine):
                succesful += 1
            else:
                # In case routine failed somewhere in the middle we should
                # reset the status pin to ensure same common point for next routine
                self.set_status_pin_low()

            repetition += 1


        # Reached when all repetitions are done
        self.boot.print_and_log('=======================================================')
        if succesful == repetition:
            self.boot.print_and_log('TEST ROUTINE FINISHED                                OK')
        else:
            self.boot.print_and_log('TEST ROUTINE FINISHED                            NOT OK')
            self.boot.print_and_log(str(succesful) + " out of " + str(self.num_rep) + " were succesful")
