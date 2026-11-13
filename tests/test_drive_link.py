import pytest

from traer_material.drive_link import LinkError, parse_drive_link

FID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_-123"


@pytest.mark.parametrize("link", [
    f"https://drive.google.com/drive/folders/{FID}?usp=sharing",
    f"https://drive.google.com/drive/u/1/folders/{FID}",
    f"drive.google.com/drive/folders/{FID}",
    f"https://drive.google.com/open?id={FID}",
    f"  {FID}  ",
])
def test_parses_folder_id(link):
    assert parse_drive_link(link).folder_id == FID


def test_resource_key():
    f = parse_drive_link(f"https://drive.google.com/drive/folders/{FID}?resourcekey=0-abc")
    assert f.resource_key == "0-abc"


@pytest.mark.parametrize("link,needle", [
    ("", "Pegá"),
    ("https://dropbox.com/s/abc", "no es de Google Drive"),
    (f"https://drive.google.com/file/d/{FID}/view", "archivo suelto"),
    ("https://drive.google.com/drive/folders/", "No pude leer"),
    ("https://drive.google.com/drive/folders/../../etc", "No pude leer"),
])
def test_rejects_bad_links(link, needle):
    with pytest.raises(LinkError, match=needle):
        parse_drive_link(link)
