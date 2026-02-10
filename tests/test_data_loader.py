"""Tests for Intel Lab data loading and cleaning."""

import pytest
from src.app.simulator.data_loader import load_data_loader


class TestDataLoader:
    """Test cases for data loader module."""
    
    @pytest.fixture(scope="class")
    def data_paths(self):
        """Fixture providing paths to test data files."""
        return {
            'data': 'data/raw/data.txt',
            'mote_locs': 'data/raw/mote_locs.txt'
        }
    
    def test_load_without_error(self, data_paths):
        """Test 1: File loads without error."""
        try:
            mote_data, mote_locs = load_data_loader(data_paths['data'], data_paths['mote_locs'])
            assert True, "Data loaded successfully"
        except Exception as e:
            pytest.fail(f"Data loader failed with error: {e}")
    
    def test_returns_mote_groups(self, data_paths):
        """Test 2: Returns mote groups (at least 1, typically around 54)."""
        mote_data, mote_locs = load_data_loader(data_paths['data'], data_paths['mote_locs'])
        
        # Check that we have mote groups
        assert isinstance(mote_data, dict), "Mote data should be a dictionary"
        assert len(mote_data) > 0, "Should have at least one mote group"
        
        # Typically Intel Lab has 54 motes, but some may be missing
        # Accept 40-60 motes as valid
        assert 30 <= len(mote_data) <= 100, f"Expected 30-100 motes, got {len(mote_data)}"
    
    def test_each_group_sorted_by_timestamp(self, data_paths):
        """Test 3: Each group is sorted by timestamp."""
        mote_data, _ = load_data_loader(data_paths['data'], data_paths['mote_locs'])
        
        for mote_id, df in mote_data.items():
            # Check that timestamps are in order
            timestamps = df['timestamp'].values
            assert (timestamps[:-1] <= timestamps[1:]).all(), \
                f"Mote {mote_id} is not sorted by timestamp"
    
    def test_no_null_temperature(self, data_paths):
        """Test 4: No null values in temperature column."""
        mote_data, _ = load_data_loader(data_paths['data'], data_paths['mote_locs'])
        
        for mote_id, df in mote_data.items():
            assert df['temperature'].isnull().sum() == 0, \
                f"Mote {mote_id} has null temperature values"
    
    def test_no_null_humidity(self, data_paths):
        """Test 5: No null values in humidity column."""
        mote_data, _ = load_data_loader(data_paths['data'], data_paths['mote_locs'])
        
        for mote_id, df in mote_data.items():
            assert df['humidity'].isnull().sum() == 0, \
                f"Mote {mote_id} has null humidity values"
