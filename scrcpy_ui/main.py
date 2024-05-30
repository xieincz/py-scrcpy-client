from argparse import ArgumentParser
from typing import Optional

from adbutils import adb
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QTimer
import scrcpy

from .ui_main import Ui_MainWindow

if not QApplication.instance():
    app = QApplication([])
else:
    app = QApplication.instance()

import os
from datetime import datetime
import time
import threading
import multiprocessing as mp

img_queue = mp.Queue()
from PySide6 import QtGui, QtCore

class Pickable_QPixmap(QtGui.QPixmap):
    def __reduce__(self):
        return type(self), (), self.__getstate__()

    def __getstate__(self):
        ba = QtCore.QByteArray()
        stream = QtCore.QDataStream(ba, QtCore.QIODevice.WriteOnly)
        stream << self
        return ba

    def __setstate__(self, ba):
        stream = QtCore.QDataStream(ba, QtCore.QIODevice.ReadOnly)
        stream >> self
        
class MainWindow(QMainWindow):
    def __init__(
        self,
        max_width: Optional[int],
        serial: Optional[str] = None,
        encoder_name: Optional[str] = None,
    ):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.max_width = max_width

        # Setup devices
        self.devices = self.list_devices()
        if serial:
            self.choose_device(serial)
        self.device = adb.device(serial=self.ui.combo_device.currentText())
        self.alive = True

        # Setup client
        self.client = scrcpy.Client(
            device=self.device,
            flip=self.ui.flip.isChecked(),
            bitrate=1000000000,
            encoder_name=encoder_name,
            max_fps=30
        )
        self.client.add_listener(scrcpy.EVENT_INIT, self.on_init)
        self.client.add_listener(scrcpy.EVENT_FRAME, self.on_frame)

        # Bind controllers
        self.ui.button_home.clicked.connect(self.on_click_home)
        self.ui.button_back.clicked.connect(self.on_click_back)

        # Bind config
        self.ui.combo_device.currentTextChanged.connect(self.choose_device)
        self.ui.flip.stateChanged.connect(self.on_flip)

        # Bind mouse event
        self.ui.label.mousePressEvent = self.on_mouse_event(scrcpy.ACTION_DOWN)
        self.ui.label.mouseMoveEvent = self.on_mouse_event(scrcpy.ACTION_MOVE)
        self.ui.label.mouseReleaseEvent = self.on_mouse_event(scrcpy.ACTION_UP)

        # Keyboard event
        self.keyPressEvent = self.on_key_event(scrcpy.ACTION_DOWN)
        self.keyReleaseEvent = self.on_key_event(scrcpy.ACTION_UP)

        self.__current_screenshot = None  # 用于在标注期间的输入后保存当前的截图

    def save_current_screenshot_v2(self, fn=None):
        # 创建一个新线程来保存图片
        thread = threading.Thread(target=self._save_current_screenshot, args=(fn,))
        thread.start()

    def _save_current_screenshot(self, fn=None):
        print("saving screenshot")
        # NOTE: 由于操作从电脑发送给手机后，还要过一段时间才会有反应，所以也许要在操作后等待一段时间再保存截图
        time.sleep(0.5)
        output_dir = "annotated_images"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if fn is None:
            fn = datetime.now().strftime(rf"%Y_%m_%d-%H_%M_%S.%f")
        output_path = os.path.join(output_dir, f"{fn}.png")
        self.__current_screenshot.save(output_path)
        print("screenshot saved")
    
    def save_current_screenshot_sleep(
        self, fn=None,time_sleep=1.5
    ):
        app.processEvents()
        #time.sleep(time_sleep)
        #self.save_current_screenshot(fn)
        QTimer.singleShot(time_sleep * 1000, lambda: self.save_current_screenshot(fn))

    def save_current_screenshot(
        self, fn=None
    ):  # NOTE: 由于操作从电脑发送给手机后，还要过一段时间才会有反应，所以也许要在操作后等待一段时间再保存截图
        app.processEvents()
        #time.sleep(1)
        output_dir = "annotated_images"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if fn is None:
            fn = datetime.now().strftime(rf"%Y_%m_%d-%H_%M_%S.%f")
        output_path = os.path.join(output_dir, f"{fn}.png")
        #self.__current_screenshot.save(output_path)
        #img_queue.put((output_path,Pickable_QPixmap(self.__current_screenshot)))
        img_queue.put((output_path,self.__current_screenshot))
        #self.device.screenshot()#.save(output_path)
        #self.save_current_xml(fn)

    def save_current_xml(self, fn=None):
        # time.sleep(0.5)
        output_dir = "annotations"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if fn is None:
            fn = datetime.now().strftime(rf"%Y_%m_%d-%H_%M_%S.%f")
        output_path = os.path.join(output_dir, f"{fn}.xml")
        # adb shell /system/bin/uiautomator dump --compressed /data/local/tmp/uidump.xml
        # adb pull /data/local/tmp/uidump.xml ./
        self.device.shell(
            f"/system/bin/uiautomator dump --compressed /data/local/tmp/uidump.xml"
        )
        self.device.sync.pull("/data/local/tmp/uidump.xml", output_path, exist_ok=True)

    def save_input(self, input_str: str):
        output_dir = "annotations"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, "log.txt")
        with open(output_path, "a") as f:
            f.write(input_str + "\n")

    def choose_device(self, device):
        if device not in self.devices:
            msgBox = QMessageBox()
            msgBox.setText(f"Device serial [{device}] not found!")
            msgBox.exec()
            return

        # Ensure text
        self.ui.combo_device.setCurrentText(device)
        # Restart service
        if getattr(self, "client", None):
            self.client.stop()
            self.client.device = adb.device(serial=device)

    def list_devices(self):
        self.ui.combo_device.clear()
        items = [i.serial for i in adb.device_list()]
        self.ui.combo_device.addItems(items)
        return items

    def on_flip(self, _):
        self.client.flip = self.ui.flip.isChecked()

    def on_click_home(self):
        # print("click home")
        log_str = """key_event,home,down"""
        self.save_input(log_str)
        print(log_str)
        self.save_current_screenshot()
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_DOWN)
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_UP)
        self.save_current_screenshot_sleep()
        log_str = """key_event,home,up"""
        self.save_input(log_str)

    def on_click_back(self):
        # print("click back")
        log_str = """key_event,back,down"""
        self.save_input(log_str)
        self.save_current_screenshot()
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_DOWN)
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_UP)
        self.save_current_screenshot_sleep()
        log_str = """key_event,back"""
        self.save_input(log_str)

    def on_mouse_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QMouseEvent):
            focused_widget = QApplication.focusWidget()
            if focused_widget is not None:
                focused_widget.clearFocus()
            ratio = self.max_width / max(self.client.resolution)
            if (
                action != scrcpy.ACTION_MOVE
            ):  # WARNING: 在真正标注数据的时候，必须要在click之后才记录move事件，而不能完全舍弃move事件
                a = action
                if a == scrcpy.ACTION_DOWN:
                    a = "down"
                elif a == scrcpy.ACTION_UP:
                    a = "up"
                if a=="down":
                    ...
                    # print(f"Mouse event: {evt.position().x() / ratio} {evt.position().y() / ratio} {a}")
                    log_str = f"mouse_event,{evt.position().x() / ratio},{evt.position().y() / ratio},{a}"
                    print(log_str)
                    self.save_input(log_str)
                    self.save_current_screenshot()
            self.client.control.touch(
                evt.position().x() / ratio, evt.position().y() / ratio, action
            )
            if (
                action != scrcpy.ACTION_MOVE
            ):  # WARNING: 在真正标注数据的时候，必须要在click之后才记录move事件，而不能完全舍弃move事件
                a = action
                if a == scrcpy.ACTION_DOWN:
                    a = "down"
                elif a == scrcpy.ACTION_UP:
                    a = "up"
                if a=="up":
                    # print(f"Mouse event: {evt.position().x() / ratio} {evt.position().y() / ratio} {a}")
                    log_str = f"mouse_event,{evt.position().x() / ratio},{evt.position().y() / ratio},{a}"
                    print(log_str)
                    self.save_input(log_str)
                    self.save_current_screenshot_sleep()

        return handler

    def on_key_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QKeyEvent):
            code = self.map_code(evt.key())
            if code != -1:
                a = action
                k = evt.key()
                if a == scrcpy.ACTION_DOWN:
                    a = "down"
                elif a == scrcpy.ACTION_UP:
                    a = "up"
                # qt keycode to string
                k = Qt.Key(k).name
                # print(f"Key event: {k} {a}")
                log_str = f"key_event,{k},{a}"
                print(log_str)
                
                if a=="down":
                    self.save_current_screenshot()
                self.client.control.keycode(code, action)
                if a=="up":
                    self.save_input(log_str)
                    self.save_current_screenshot_sleep()

        return handler

    def map_code(self, code):
        """
        Map qt keycode ti android keycode

        Args:
            code: qt keycode
            android keycode, -1 if not founded
        """

        if code == -1:
            return -1
        if 48 <= code <= 57:
            return code - 48 + 7
        if 65 <= code <= 90:
            return code - 65 + 29
        if 97 <= code <= 122:
            return code - 97 + 29

        hard_code = {
            32: scrcpy.KEYCODE_SPACE,
            16777219: scrcpy.KEYCODE_DEL,
            16777248: scrcpy.KEYCODE_SHIFT_LEFT,
            16777220: scrcpy.KEYCODE_ENTER,
            16777217: scrcpy.KEYCODE_TAB,
            16777249: scrcpy.KEYCODE_CTRL_LEFT,
        }
        if code in hard_code:
            return hard_code[code]

        print(f"Unknown keycode: {code}")
        return -1

    def on_init(self):
        self.setWindowTitle(f"Serial: {self.client.device_name}")

    def on_frame(self, frame):#这里的frame其实是frame = cv2.flip(frame, 1)
        app.processEvents()
        if frame is not None:
            self.__current_screenshot = frame
            ratio = self.max_width / max(self.client.resolution)
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.shape[1] * 3,
                QImage.Format_BGR888,
            )
            #self.__current_screenshot = image  # 保存当前的截图
            pix = QPixmap(image)
            pix.setDevicePixelRatio(1 / ratio)
            self.ui.label.setPixmap(pix)
            self.resize(1, 1)

    def closeEvent(self, _):
        self.client.stop()
        self.alive = False

import shutil

def save_img_queue(img_queue):
    while True:
        if not img_queue.empty():
            output_path, img = img_queue.get()
            img=image = QImage(
                img,
                img.shape[1],
                img.shape[0],
                img.shape[1] * 3,
                QImage.Format_BGR888,
            )
            img.save(output_path)
            print("screenshot saved")
        time.sleep(0.1)
    exit(0)
process=None
def main():
    annotation_dirs=["annotations","annotated_images"]
    fn = datetime.now().strftime(rf"%Y_%m_%d-%H_%M_%S.%f")
    for dn in annotation_dirs:
        if os.path.exists(dn):
            print("saving existing annotations and annotated images to",fn)
            os.makedirs(fn)
            for dn in annotation_dirs:
                if os.path.exists(dn):
                    shutil.move(dn,fn)
            print("saved existing annotations and annotated images to",fn)
            break
    process=mp.Process(target=save_img_queue,args=(img_queue,))
    process.daemon=True
    process.start()
    parser = ArgumentParser(description="A simple scrcpy client")
    parser.add_argument(
        "-m",
        "--max_width",
        type=int,
        default=800,
        help="Set max width of the window, default 800",
    )
    parser.add_argument(
        "-d",
        "--device",
        type=str,
        help="Select device manually (device serial required)",
    )
    parser.add_argument("--encoder_name", type=str, help="Encoder name to use")
    args = parser.parse_args()

    m = MainWindow(args.max_width, args.device, args.encoder_name)
    m.show()

    m.client.start()
    while m.alive:
        m.client.start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        if process:
            process.terminate()
        print("exit")
        exit(0)
