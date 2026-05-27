from app.security.password import hash_password, validate_password_strength, verify_password


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "CorrectHorseBatteryStaple1"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$argon2id$")
        assert verify_password(plain, hashed)
        assert not verify_password("WrongPassword1", hashed)

    def test_hash_is_deterministic_salt(self):
        h1 = hash_password("SamePassword1")
        h2 = hash_password("SamePassword1")
        assert h1 != h2  # different salts


class TestPasswordStrength:
    def test_too_short(self):
        valid, err = validate_password_strength("Ab1")
        assert not valid
        assert err == "errors.password_too_short"

    def test_missing_uppercase(self):
        valid, err = validate_password_strength("abcdefgh1")
        assert not valid
        assert err == "errors.password_too_weak"

    def test_missing_lowercase(self):
        valid, err = validate_password_strength("ABCDEFGH1")
        assert not valid
        assert err == "errors.password_too_weak"

    def test_missing_digit(self):
        valid, err = validate_password_strength("Abcdefgh")
        assert not valid
        assert err == "errors.password_too_weak"

    def test_common_password(self):
        valid, err = validate_password_strength("Password1")
        assert not valid  # too common
        assert err == "errors.password_too_weak"

    def test_strong_password(self):
        valid, err = validate_password_strength("MyC0rrectHorseBattery!")
        assert valid
        assert err is None

    def test_max_length_accepted(self):
        # 128-char strong password — zxcvbn only checks first 72 chars
        # First 72 must be strong: 4 words + digits + upper
        pwd = "Correct-Horse-Battery-Staple$1" + "z" * 98
        assert len(pwd) == 128
        valid, err = validate_password_strength(pwd)
        assert valid
        assert err is None

    def test_too_long(self):
        valid, err = validate_password_strength("A" * 128 + "b1")
        assert not valid
        assert err == "errors.password_too_long"
