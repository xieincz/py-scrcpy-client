# Python Scrcpy Client
This package allows you to view and control android device in realtime.



## How to use
建议使用 python 3.10

To begin with, you need to install this package via pip:

```shell
pip install -r requirements.txt
```


## 运行方法

```bash
adb devices
python -m scrcpy_ui.main
```

注：每标注完一个task都要手动将当前目录下的 annotated_images 和 annotations 文件夹移动到别处，以免被下一次task的标注所覆盖。执行完当前task的最后一步之后请等待5秒左右，以确保最后一张截图能被顺利保存。

注：只需要鼠标/键盘在电脑上进行操作即可，只会记录在电脑上的操作。如果需要关闭广告/弹窗，可以直接用手指点击手机屏幕，这样就不会被记录下来。



## Contribution & Development
Already implemented all functions in scrcpy server 1.20.  
Please check scrcpy server 1.20 source code: [Link](https://github.com/Genymobile/scrcpy/tree/v1.20/server)

## Reference & Appreciation
- Core: [scrcpy](https://github.com/Genymobile/scrcpy)
- Idea: [py-android-viewer](https://github.com/razumeiko/py-android-viewer)
- CI: [index.py](https://github.com/index-py/index.py)
