import { useState, useMemo } from 'react';
import { LimitOffsetParams } from '@/lib/api';

export interface UseDataTableProps {
  initialPage?: number;
  initialPageSize?: number;
  onPageChange?: (page: number) => void;
}

export function useDataTable({
  initialPage = 1,
  initialPageSize = 50,
  onPageChange,
}: UseDataTableProps = {}) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const paginationParams = useMemo<LimitOffsetParams>(() => ({
    limit: pageSize,
    offset: (page - 1) * pageSize,
  }), [page, pageSize]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    onPageChange?.(newPage);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1); // Reset to first page when changing size
    onPageChange?.(1);
  };

  return {
    page,
    pageSize,
    setPage: handlePageChange,
    setPageSize: handlePageSizeChange,
    limit: paginationParams.limit,
    offset: paginationParams.offset,
  };
}
