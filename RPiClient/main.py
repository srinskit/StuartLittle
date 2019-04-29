#! /usr/bin/python3
import RPi.GPIO as GPIO
import picamera
import time
import sys
import io
import logging
import socketserver
import requests
from threading import Condition, Thread
from http import server
from Rach import Rach
run = True
servo = None
driver = None


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


output = StreamingOutput()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header(
                'Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class Driver:
    def __init__(self, motor_left, motor_right):
        self.motor_l = motor_left
        self.motor_r = motor_right
        for pin in (motor_left+motor_right):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

    def rotate_l(self):
        GPIO.output(self.motor_l[1], GPIO.HIGH)
        GPIO.output(self.motor_l[0], GPIO.HIGH)
        GPIO.output(self.motor_r[0], GPIO.LOW)
        GPIO.output(self.motor_r[1], GPIO.HIGH)

    def rotate_r(self):
        GPIO.output(self.motor_l[1], GPIO.LOW)
        GPIO.output(self.motor_l[0], GPIO.HIGH)
        GPIO.output(self.motor_r[0], GPIO.HIGH)
        GPIO.output(self.motor_r[1], GPIO.HIGH)

    def forward(self):
        GPIO.output(self.motor_l[0], GPIO.HIGH)
        GPIO.output(self.motor_l[1], GPIO.LOW)
        GPIO.output(self.motor_r[1], GPIO.HIGH)
        GPIO.output(self.motor_r[0], GPIO.LOW)

    def reverse(self):
        GPIO.output(self.motor_l[0], GPIO.LOW)
        GPIO.output(self.motor_l[1], GPIO.HIGH)
        GPIO.output(self.motor_r[1], GPIO.LOW)
        GPIO.output(self.motor_r[0], GPIO.HIGH)

    def stop(self):
        for pin in (self.motor_l+self.motor_r):
            GPIO.output(pin, GPIO.HIGH)


def test_driver(driver):
    driver.forward()
    time.sleep(5)
    driver.stop()
    time.sleep(5)
    driver.reverse()
    time.sleep(5)
    driver.stop()
    time.sleep(5)
    driver.left()
    time.sleep(5)
    driver.stop()
    time.sleep(5)
    driver.right()
    time.sleep(5)
    driver.stop()


def bns_register(bns_server, bot_name):
    while run:
        try:
            requests.post("http://%s:3000/bns/register" %
                          bns_server, data={'bot_name': bot_name})
        except:
            pass
        finally:
            time.sleep(10)


def turn_view(cycle):
    servo.ChangeDutyCycle(cycle)
    time.sleep(0.05)


def set_drive(cmd):
    if cmd == "w":
        driver.forward()
        time.sleep(0.1)
        driver.stop()
    elif cmd == "a":
        driver.rotate_l()
        time.sleep(0.1)
        driver.stop()
    elif cmd == "s":
        driver.reverse()
        time.sleep(0.1)
        driver.stop()
    elif cmd == "d":
        driver.rotate_r()
        time.sleep(0.1)
        driver.stop()


def main():
    global run, servo, driver
    bns_server = sys.argv[2]
    bot_name = sys.argv[1]
    motor_left, motor_right = (24, 23), (8, 25)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(18, GPIO.OUT)
    servo = GPIO.PWM(18, 50)
    servo.start(7.5)
    driver = Driver(motor_left,  motor_right)
    bns_thread = Thread(target=bns_register, args=[bns_server, bot_name])
    with picamera.PiCamera(resolution='640x480', framerate=24) as camera:
        camera.annotate_background = picamera.Color('black')
        # camera.annotate_text = str(int(time.time()))
        camera.start_recording(output, format='mjpeg')
        rach = Rach("ws://%s:8080" % bns_server,
                    {'username': '', 'password': ''})
        try:
            rach.start()
            time.sleep(2)
            rach.add_sub('/bots/%s/view' %
                         bot_name, lambda x: turn_view(x["data"]), [])
            rach.add_sub('/bots/%s/drive' %
                         bot_name, lambda x: set_drive(x["data"]), [])
            bns_thread.start()
            server = StreamingServer(('', 8000), StreamingHandler)
            server.serve_forever()
        except:
            pass
        finally:
            run = False
            servo.stop()
            rach.stop()
            server.shutdown()
            camera.stop_recording()
            GPIO.cleanup()
            bns_thread.join()
            print("Bye")


if __name__ == "__main__":
    main()
