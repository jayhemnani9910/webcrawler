"""Tests for Vault KMS provider verification functionality."""
import sys
import os
import base64

# Ensure src directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import Mock, MagicMock, patch, create_autospec


class _RealTransitShape:
    """Mirrors the parameter names of hvac's real
    Transit.sign_data/verify_signed_data (checked against hvac 2.4.0), so an
    autospec'd mock rejects a call that doesn't match hvac's actual API --
    unlike a bare Mock/MagicMock, which silently accepts any attribute or
    kwarg regardless of whether it exists on the real client.
    """
    def sign_data(self, name, hash_input=None, key_version=None,
                  hash_algorithm=None, context=None, prehashed=None,
                  signature_algorithm=None, marshaling_algorithm=None,
                  salt_length=None, mount_point='transit', batch_input=None):
        raise NotImplementedError

    def verify_signed_data(self, name, hash_input, signature=None, hmac=None,
                            hash_algorithm=None, context=None, prehashed=None,
                            signature_algorithm=None, salt_length=None,
                            marshaling_algorithm=None, mount_point='transit'):
        raise NotImplementedError


def _mock_vault_client():
    """Build a mock hvac.Client whose secrets.transit surface is autospec'd
    against hvac's real method shape, so a wrong kwarg or method name would
    raise instead of silently succeeding."""
    mock_client = Mock()
    mock_client.secrets.transit = create_autospec(_RealTransitShape, instance=True)
    return mock_client


class TestVaultVerify:
    """Test suite for VaultProvider.verify() method."""

    def test_vault_verify_returns_true_for_valid_signature(self):
        """Test that verify() returns True when Vault confirms signature is valid."""
        # Create a mock hvac module
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client
        mock_client.secrets.transit.verify_signed_data.return_value = {
            'data': {'valid': True}
        }

        # Patch hvac in sys.modules before importing keys_kms
        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                # Force reimport to pick up mocked hvac
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                data = b'test data'
                signature = b'vault:v1:VALID_SIGNATURE'

                result = provider.verify('test-key', data, signature)

                assert result is True
                mock_client.secrets.transit.verify_signed_data.assert_called_once_with(
                    name='test-key',
                    hash_input=base64.b64encode(data).decode('ascii'),
                    signature='vault:v1:VALID_SIGNATURE'
                )

    def test_vault_verify_returns_false_for_invalid_signature(self):
        """Test that verify() returns False when Vault confirms signature is invalid."""
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client
        mock_client.secrets.transit.verify_signed_data.return_value = {
            'data': {'valid': False}
        }

        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                data = b'test data'
                signature = b'vault:v1:INVALID_SIGNATURE'

                result = provider.verify('test-key', data, signature)

                assert result is False

    def test_vault_verify_returns_false_when_vault_unavailable(self):
        """Test that verify() returns False when Vault is unavailable or errors."""
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client
        mock_client.secrets.transit.verify_signed_data.side_effect = Exception('Vault connection failed')

        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                data = b'test data'
                signature = b'vault:v1:SOME_SIGNATURE'

                result = provider.verify('test-key', data, signature)

                # Should return False instead of raising exception
                assert result is False

    def test_vault_verify_handles_missing_valid_field(self):
        """Test that verify() returns False when response is missing 'valid' field."""
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client
        mock_client.secrets.transit.verify_signed_data.return_value = {
            'data': {}  # Missing 'valid' field
        }

        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                data = b'test data'
                signature = b'vault:v1:SOME_SIGNATURE'

                result = provider.verify('test-key', data, signature)

                # Should return False when 'valid' field is missing
                assert result is False

    def test_vault_sign_and_verify_integration(self):
        """Test that a signature created by sign() can be verified by verify()."""
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client

        # Mock sign_data to return a signature
        mock_client.secrets.transit.sign_data.return_value = {
            'data': {'signature': 'vault:v1:TEST_SIGNATURE'}
        }

        # Mock verify_signed_data to return valid for this signature
        mock_client.secrets.transit.verify_signed_data.return_value = {
            'data': {'valid': True}
        }

        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                data = b'integration test data'

                # Sign the data
                signature = provider.sign('test-key', data)
                assert signature == b'vault:v1:TEST_SIGNATURE'

                # Verify the signature
                result = provider.verify('test-key', data, signature)
                assert result is True

    def test_vault_verify_with_different_data_returns_false(self):
        """Test that verify() returns False when data doesn't match signature."""
        mock_hvac = MagicMock()
        mock_client = _mock_vault_client()
        mock_hvac.Client.return_value = mock_client

        # Vault would return False for mismatched data
        mock_client.secrets.transit.verify_signed_data.return_value = {
            'data': {'valid': False}
        }

        with patch.dict(sys.modules, {'hvac': mock_hvac}):
            with patch.dict(os.environ, {
                'VAULT_ADDR': 'http://localhost:8200',
                'VAULT_TOKEN': 'test-token'
            }):
                if 'src.keys_kms' in sys.modules:
                    del sys.modules['src.keys_kms']
                from src.keys_kms import get_provider

                provider = get_provider()
                different_data = b'different data'
                signature = b'vault:v1:SIGNATURE_FOR_ORIGINAL'

                # Verify with different data should return False
                result = provider.verify('test-key', different_data, signature)
                assert result is False
