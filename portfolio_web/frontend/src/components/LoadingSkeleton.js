/**
 * LoadingSkeleton Component
 * Provides elegant loading placeholders with shimmer animation
 */
import React from 'react';
import './LoadingSkeleton.css';

export const LoadingSkeleton = ({ 
  width = '100%', 
  height = '20px', 
  borderRadius = '4px',
  variant = 'text', // text, circular, rectangular, card
  count = 1,
  className = ''
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'circular':
        return { width: height, borderRadius: '50%' };
      case 'card':
        return { height: '200px', borderRadius: '8px' };
      case 'rectangular':
        return { borderRadius: '8px' };
      default:
        return { borderRadius };
    }
  };

  const skeletonStyle = {
    width,
    height,
    ...getVariantStyles()
  };

  return (
    <>
      {[...Array(count)].map((_, index) => (
        <div
          key={index}
          className={`loading-skeleton ${className}`}
          style={skeletonStyle}
        />
      ))}
    </>
  );
};

export const TableSkeleton = ({ rows = 5, columns = 4 }) => {
  return (
    <div className="table-skeleton">
      {/* Header */}
      <div className="table-skeleton-header">
        {[...Array(columns)].map((_, i) => (
          <LoadingSkeleton key={`header-${i}`} height="16px" width="80%" />
        ))}
      </div>
      
      {/* Rows */}
      {[...Array(rows)].map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="table-skeleton-row">
          {[...Array(columns)].map((_, colIndex) => (
            <LoadingSkeleton 
              key={`cell-${rowIndex}-${colIndex}`} 
              height="14px" 
              width={colIndex === 0 ? '60%' : '40%'}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

export const CardSkeleton = () => {
  return (
    <div className="card-skeleton">
      <LoadingSkeleton height="24px" width="60%" className="mb-3" />
      <LoadingSkeleton height="40px" width="80%" className="mb-2" />
      <LoadingSkeleton height="16px" width="50%" />
    </div>
  );
};

export const PortfolioSkeleton = () => {
  return (
    <div className="portfolio-skeleton">
      <div className="portfolio-skeleton-header">
        <LoadingSkeleton height="32px" width="200px" className="mb-2" />
        <LoadingSkeleton height="16px" width="300px" />
      </div>
      
      <div className="portfolio-skeleton-stats">
        {[...Array(4)].map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
      
      <div className="portfolio-skeleton-chart">
        <LoadingSkeleton variant="card" />
      </div>
      
      <TableSkeleton rows={8} columns={6} />
    </div>
  );
};

export default LoadingSkeleton;
