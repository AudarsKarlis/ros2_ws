from threading import Thread, Event
import time
import datetime

class anim:
    def __init__(self, symbols):
        self.symbols = symbols
        self.__finished = False
        self.__threadEvent = Event()
        self.__thread = Thread(target=self.anim)

    def start(self):
        self.__thread.start()

    @property
    def finished(self):
        return self.__finished

    @finished.setter
    def finished(self, finished):
        if isinstance(finished, bool):
            self.__finished = finished
            if finished:
                self.__threadEvent.set()
                time.sleep(0.1)
        else:
            raise ValueError

    def anim(self):
        i=0
        start_time = datetime.datetime.now().strftime("%H:%M:%S")
        while not self.__finished:
            i = (i+1) % len(self.symbols)
            print('\r\033[K%s \33[1000C\33[20D%s/%s' % (self.symbols[i], start_time, datetime.datetime.now().strftime("%H:%M:%S")), flush=True, end='')
            self.__threadEvent.wait(1/len(self.symbols))
            self.__threadEvent.clear()
        print("\r\033[K Finished!!!")
        del self.__thread
        

def loading_anim_circle(func, *args):
    symbols = ['⣾', '⣷', '⣯', '⣟', '⡿', '⢿', '⣻', '⣽']
    anim_thread = anim(symbols)
    anim_thread.start()
    data = func(*args)
    anim_thread.finished = True
    return data

def loading_anim_line(func, *args):
    symbols = ['|', '/', '-', '\\', '|', '/', '-', '\\']
    anim_thread = anim(symbols)
    anim_thread.start()
    data = func(*args)
    anim_thread.finished = True
    return data

def loading_anim_bar(func, *args):
    symbols = [
               " [=     ]",
               " [ =    ]",
               " [  =   ]",
               " [   =  ]",
               " [    = ]",
               " [     =]",
               " [    = ]",
               " [   =  ]",
               " [  =   ]",
               " [ =    ]",
    ]
    anim_thread = anim(symbols)
    anim_thread.start()
    data = func(*args)
    anim_thread.finished = True
    return data


def loading_anim_bar2(func, *args):
    symbols = [
               "[        ]",
               "[=       ]",
               "[===     ]",
               "[====    ]",
               "[=====   ]",
               "[======  ]",
               "[======= ]",
               "[========]",
               "[ =======]",
               "[  ======]",
               "[   =====]",
               "[    ====]",
               "[     ===]",
               "[      ==]",
               "[       =]",
               "[        ]",
               "[        ]"
    ]
    anim_thread = anim(symbols)
    anim_thread.start()
    data = func(*args)
    anim_thread.finished = True
    return data

