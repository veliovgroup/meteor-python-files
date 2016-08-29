Meteor-pyfiles
=====

Official pyfiles (*to be used within* [ostrio:files](https://github.com/VeliovGroup/Meteor-Files)) package for [python-meteor](https://github.com/hharnisc/python-meteor) client.

## Usage
```python
from MeteorClient import MeteorClient
from MeteorFiles import Uploader
import time

client = MeteorClient('ws://127.0.0.1:3000/websocket')
client.connect()

# upload example, work with Meteor-Files example: demo-simplest-upload
# server code: https://github.com/VeliovGroup/Meteor-Files/tree/master/demo-simplest-upload
client.subscribe('files.images.all');

uploader = Uploader(client, 'Images', transport='http', verbose=True)

uploader.upload("test.jpeg")
while not uploader.finished:
    time.sleep(0.1)

```
## Speed test
* File size:345770885 (~345MB)
* transport='http': 26.8s
* transport='ddp': 110.1s

__Status__: `dev`, `not-stable`, `not-published`
