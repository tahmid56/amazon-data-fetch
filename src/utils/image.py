from io import BytesIO

import numpy as np
import requests

from PIL import Image

from tensorflow.keras.applications.vgg16 import (
    preprocess_input,
)

from tensorflow.keras.preprocessing import image as keras_image

from config import settings


def load_image_from_url(url):
    if not url or not isinstance(url, str) or url.strip() == "":
        return None
    try:
        response = requests.get(url, timeout=5)
        img = Image.open(BytesIO(response.content)).convert('RGB')
        return img
    except:
        return None


def preprocess_image_for_vgg(
    image,
    target_size=(224, 224),
):

    image = image.resize(target_size)

    array = keras_image.img_to_array(
        image
    )

    array = np.expand_dims(
        array,
        axis=0,
    )

    return preprocess_input(array)