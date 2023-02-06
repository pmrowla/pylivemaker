import pytest

from livemaker.lsb import novel


def test_padding_is_none():
    # This throws a type error
    with pytest.raises(TypeError):
        int(None)

    # Passing nothing is fine
    novel.TWdOpeDiv()

    # Explicitly passing None will bypass the parameter defaults of 0
    novel.TWdOpeDiv(padright=None, padleft=None, align=None, noheight=None)


if __name__ == "__main__":
    test_padding_is_none()
