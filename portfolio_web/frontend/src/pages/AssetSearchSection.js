import React from 'react';
import { FiSearch } from 'react-icons/fi';
import { LoadingSkeleton } from '../components';

const AssetSearchSection = ({
  searchValue,
  onSearchChange,
  assetFilter,
  onFilterChange,
  marketFilter,
  onMarketChange,
  marketOptions,
  financialSectorFilter,
  onFinancialSectorChange,
  financialSectorOptions,
  items,
  onSelect,
  loading,
  selectedTickers
}) => {
  const filterOptions = [
    { value: 'all', label: 'All' },
    { value: 'stock', label: 'Stocks' },
    { value: 'etf', label: 'ETFs' },
    { value: 'bond', label: 'Bonds' },
    { value: 'crypto', label: 'Crypto' },
    { value: 'commodity', label: 'Commodities' }
  ];

  return (
    <>
      <div className="pb-step-head pb-search-step-head">
        <span className="pb-step-index">2</span>
        <h3 className="pb-sub-title">Add Holdings</h3>
      </div>
      <p className="pb-help-text">Tip: search by ticker or company name, then press Enter to add the highlighted result.</p>
      <div className="form-group pb-compact-group">
        <label className="pb-label-row">
          <FiSearch size={14} />
          Security Search
        </label>
        {loading ? (
          <LoadingSkeleton height="44px" borderRadius="8px" />
        ) : (
          <input
            type="text"
            placeholder="Search ticker or security name..."
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            className="form-control pb-input-lg"
          />
        )}
      </div>

      <div className="pb-filter-chip-row">
        {filterOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`pb-filter-chip ${assetFilter === option.value ? 'active' : ''}`}
            onClick={() => onFilterChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="pb-search-filter-row">
        <label className="pb-search-filter-label" htmlFor="market-filter-select">
          Market
        </label>
        <select
          id="market-filter-select"
          className="form-control pb-search-filter-select"
          value={marketFilter}
          onChange={(event) => onMarketChange(event.target.value)}
        >
          <option value="all">All Markets</option>
          {(marketOptions || []).map((market) => (
            <option key={market} value={market}>{market}</option>
          ))}
        </select>

        <label className="pb-search-filter-label" htmlFor="financial-sector-filter-select">
          Sector
        </label>
        <select
          id="financial-sector-filter-select"
          className="form-control pb-search-filter-select"
          value={financialSectorFilter}
          onChange={(event) => onFinancialSectorChange(event.target.value)}
        >
          <option value="all">All Sectors</option>
          {(financialSectorOptions || []).map((sector) => (
            <option key={sector} value={sector.toLowerCase()}>{sector}</option>
          ))}
        </select>
      </div>

      <div className="pb-search-results pb-search-results-lg">
        {loading ? (
          <div className="pb-loading-box">
            <LoadingSkeleton count={5} height="40px" style={{ marginBottom: '8px' }} />
          </div>
        ) : items.length > 0 ? items.map((item) => {
          const isSelected = selectedTickers.has(item.ticker);
          return (
            <button
              key={item.ticker}
              type="button"
              onClick={() => onSelect(item)}
              className={`pb-security-row ${isSelected ? 'selected' : ''}`}
              aria-label={`${isSelected ? 'Added' : 'Add'} ${item.ticker} ${item.name || ''}`}
            >
              <div>
                <div className="pb-security-ticker">{item.ticker}</div>
                <div className="pb-security-name">{item.name?.substring(0, 42)}</div>
              </div>
              <div className="pb-security-mark">{isSelected ? 'Added' : 'Add'}</div>
            </button>
          );
        }) : (
          <div className="pb-empty-text">No matching securities found</div>
        )}
      </div>
    </>
  );
};

export default AssetSearchSection;
