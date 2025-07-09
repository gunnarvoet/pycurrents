from pycurrents.ladcp.ladcp import Profile
import pytest

def test_init_profile_file_not_found():
    with pytest.raises(FileNotFoundError) as exc_info:
        _ = Profile("ThisFileDoesntExist.txt")

    assert "No such file or directory" in str(exc_info.value), "Profile init did not throw expected exception"


