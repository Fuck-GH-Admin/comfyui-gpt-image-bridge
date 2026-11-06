from __future__ import annotations

import base64
import io

import numpy as np
import pytest
import torch
from PIL import Image

from conftest import image_tensor
from gpt_image_bridge import images
from gpt_image_bridge.errors import BridgeError
from gpt_image_bridge import session_credentials


def encoded_image(mode='RGB', image_format='PNG', size=(9, 7)):
    buffer = io.BytesIO()
    color = (25, 75, 125, 0) if mode == 'RGBA' else (25, 75, 125)
    Image.new(mode, size, color).save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.mark.parametrize('image_format', ['PNG', 'JPEG', 'WEBP'])
def test_output_formats_decode_to_comfy_image(image_format):
    payload = encoded_image(image_format=image_format)
    _, metadata = images.validate_image_bytes(payload)
    tensor = images.image_bytes_to_tensor([payload])
    assert metadata['format'] == image_format
    assert tensor.shape == (1, 7, 9, 3)
    assert tensor.dtype == torch.float32
    assert 0 <= tensor.min() <= tensor.max() <= 1


@pytest.mark.xfail(strict=True, reason='Transparent output loses alpha in image_bytes_to_tensor; needs an explicit alpha output contract.')
def test_transparent_image_preserves_alpha_at_comfy_boundary():
    tensor = images.image_bytes_to_tensor([encoded_image(mode='RGBA')])
    assert tensor.shape[-1] == 4
    assert torch.all(tensor[..., 3] == 0)


def test_different_dimensions_cannot_silently_form_a_batch():
    with pytest.raises(ValueError, match='different dimensions'):
        images.image_bytes_to_tensor([encoded_image(), encoded_image(size=(8, 8))])
    with pytest.raises(ValueError, match='No output'):
        images.image_bytes_to_tensor([])


@pytest.mark.parametrize('payload', [b'', b'not-an-image', b'\x89PNG\r\n\x1a\n'])
def test_invalid_output_payload_is_rejected(payload):
    with pytest.raises(ValueError):
        images.validate_image_bytes(payload)


def test_output_byte_pixel_and_mime_limits(monkeypatch):
    payload = encoded_image()
    with pytest.raises(ValueError, match='byte safety limit'):
        images.validate_image_bytes(payload, max_bytes=1)
    with pytest.raises(ValueError, match='MIME'):
        images.validate_image_bytes(payload, content_type='text/html')
    monkeypatch.setattr(images, 'MAX_IMAGE_PIXELS', 10)
    with pytest.raises(ValueError, match='dimensions'):
        images.validate_image_bytes(payload)


def test_base64_data_url_and_invalid_input():
    payload = encoded_image()
    url = 'data:image/png;base64,' + base64.b64encode(payload).decode()
    assert images.b64_image_to_bytes(url)[0] == payload
    with pytest.raises(ValueError, match='base64'):
        images.b64_image_to_bytes('not%base64')


@pytest.mark.parametrize('channels', [1, 3, 4])
def test_input_channel_layout_and_clamping(channels):
    tensor = torch.zeros((1, 3, 5, channels))
    tensor[:, :, 0, :] = -1
    tensor[:, :, -1, :] = 2
    image = images.tensor_to_png(tensor)
    with Image.open(io.BytesIO(image.png_bytes)) as decoded:
        pixels = np.asarray(decoded)
        assert decoded.size == (5, 3)
        assert pixels[:, 0].max() == 0
        assert pixels[:, -1].min() == 255
        assert decoded.mode == ('RGBA' if channels == 4 else 'RGB')


def test_invalid_input_layout_and_mask_layout():
    with pytest.raises(ValueError, match='one IMAGE'):
        images.tensor_to_png(image_tensor(4, 5).repeat(2, 1, 1, 1))
    with pytest.raises(ValueError, match='layout'):
        images.tensor_to_png(torch.zeros((1, 4, 5, 2)))
    with pytest.raises(ValueError, match='dimensions'):
        images.encode_reference_slots(torch.zeros((4, 5)))
    with pytest.raises(ValueError, match='start_slot'):
        images.encode_reference_slots(start_slot=0)
    with pytest.raises(ValueError, match='start_slot'):
        images.renumber_references([], start_slot=0)
    with pytest.raises(ValueError):
        images.mask_to_png(None)
    with pytest.raises(ValueError, match='layout'):
        images.mask_to_png(torch.zeros((1, 1, 3, 4)))


def test_mask_samples_keep_orientation_and_intensity():
    mask = torch.tensor([[[0., 1.], [0.5, 0.25]]])
    with Image.open(io.BytesIO(images.mask_to_png(mask))) as decoded:
        assert decoded.size == (2, 2)
        assert np.asarray(decoded).tolist() == [[0, 255], [128, 64]]


def test_session_capacity_evicts_oldest_and_rejects_oversized_secret(monkeypatch):
    monkeypatch.setattr(session_credentials, '_CREDENTIALS', {})
    monkeypatch.setattr(session_credentials, 'MAX_SESSION_CREDENTIALS', 2)
    first = session_credentials.issue_session_credential('first', now=1)
    second = session_credentials.issue_session_credential('second', now=2)
    third = session_credentials.issue_session_credential('third', now=3)
    with pytest.raises(BridgeError, match='session_credential_missing'):
        session_credentials.consume_session_credential(first, now=4)
    assert session_credentials.consume_session_credential(second, now=4) == 'second'
    assert session_credentials.consume_session_credential(third, now=4) == 'third'
    with pytest.raises(ValueError, match='too large'):
        session_credentials.issue_session_credential('a' * (16 * 1024 + 1))
