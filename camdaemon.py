from time import sleep
from pymongo import MongoClient
from picamera import PiCamera
from datetime import datetime
from awslib import AwsHelper
import os
import threading
from subprocess import call
import RPi.GPIO as GPIO
from core import setup_logging
import json
from scan import getserver

folder = "/home/pi/Documents/videos"
camera_name = "Driveway"
green_led = 11
red_led = 7
log = setup_logging(name="camera daemon",fileName="/home/pi/Documents/log/camdaemon.log")

setup = lambda led : GPIO.setup(led, GPIO.OUT)
turn_on = lambda led : GPIO.output(led,1)
turn_off = lambda led : GPIO.output(led,0)

def setup_GPIO(led):
        setup(led)
        turn_on(led)

def capture_ex(fun):
	"""
		decorator to put try catch around a function call and print exception message
	"""
	def wrapper(*args, **kwargs):
		try:
			return fun(*args,**kwargs)
		except Exception as ex:
			log.error("exception at {0} msg: {1}", fun, str(ex))
	return wrapper

def sorted_ls(path):
        mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
        return list(sorted(os.listdir(path), key=mtime))

def convert(filename):
        mp4name = filename.replace("h264","mp4")
        call(["MP4Box","-add", filename, mp4name])
        return mp4name

class CleanerThread(threading.Thread):

        def __init__(self, filename):
                self.file = filename
                self.aws = AwsHelper()
                super(CleanerThread, self).__init__()

        @capture_ex
        def process_file(self):
                mp4name = convert(self.file)
                os.remove(self.file)
                log.info("Uploading to AWS : %s"  % mp4name)
                self.aws.upload(mp4name)
                os.remove(mp4name)
               

        @capture_ex        
        def run(self):
        	self.process_file()
                        
                

class DashCamThread(threading.Thread):

        def __init__(self,video_length, number_to_keep,state, folder):
                self.duration = video_length
                self.files_to_keep = number_to_keep
                self.cam = PiCamera()
                self.state = state
                self.folder = folder
                super(DashCamThread,self).__init__()

        def get_file_name(self):
                timestamp = lambda : datetime.now().strftime("%Y%m%d_%H%M%s")
                
                while True:
                        
                        if self.state["Mode"] == 'dashcam':
                                filename =  str.format("{0}_{1}.h264", camera_name, timestamp())
                                yield os.path.join(self.folder, filename)
                        else:
                                #turn_off(red_led)
                                yield None
                        sleep(0.1)
                        
        @capture_ex        
        def run(self):
                try:
                        for filename in self.get_file_name():
                                if filename:
                                        log.info("recording %s " % filename)
                                        self.state["current_file"] = filename
                                        self.cam.start_recording(filename)
                                        self.cam.wait_recording(self.duration)
                                        self.cam.stop_recording()
                                        cleaner = CleanerThread(filename)
                                        cleaner.start()
                except Exception as ex:
                        log.error(ex)
                        turn_off(green_led)
                        turn_on(red_led)
                                
                

        
        
if __name__ == '__main__':
       
        log.info("starting camera daemone")


        GPIO.setmode(GPIO.BOARD)

        setup_GPIO(green_led)
        log.info("LED Setup")

        camstate = {"Mode":"dashcam","current_file":"None"}
        
        camthread = DashCamThread(180, 1,camstate, folder)
      
        log.info("Starting main threads")

        camthread.start()
 
      
 
     

                
      

        
        

