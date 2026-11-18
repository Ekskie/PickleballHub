"""
In-memory mock Supabase PostgREST database engine for unit and integration testing.
Provides query-builder chaining compatible with the official supabase-py SDK.
"""

import copy
import uuid

class MockResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count

class MockQueryBuilder:
    def __init__(self, table_name, rows_store):
        self.table_name = table_name
        self.rows_store = rows_store
        self.filters = []
        self._is_single = False
        self._limit = None
        self._order_col = None
        self._order_desc = False
        self._operation = 'select'
        self._insert_data = None
        self._update_data = None
        self._count_exact = False

    def select(self, columns='*', count=None):
        self._operation = 'select'
        if count == 'exact':
            self._count_exact = True
        return self

    def eq(self, column, value):
        self.filters.append(lambda r: str(r.get(column)) == str(value) if r.get(column) is not None else value is None)
        return self

    def neq(self, column, value):
        self.filters.append(lambda r: str(r.get(column)) != str(value) if r.get(column) is not None else value is not None)
        return self

    def in_(self, column, values):
        val_strs = {str(v) for v in values}
        self.filters.append(lambda r: str(r.get(column)) in val_strs)
        return self

    def gte(self, column, value):
        self.filters.append(lambda r: (r.get(column) is not None) and str(r.get(column)) >= str(value))
        return self

    def gt(self, column, value):
        self.filters.append(lambda r: (r.get(column) is not None) and str(r.get(column)) > str(value))
        return self

    def lte(self, column, value):
        self.filters.append(lambda r: (r.get(column) is not None) and str(r.get(column)) <= str(value))
        return self

    def lt(self, column, value):
        self.filters.append(lambda r: (r.get(column) is not None) and str(r.get(column)) < str(value))
        return self

    def order(self, column, desc=False):
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._is_single = True
        return self

    def insert(self, data):
        self._operation = 'insert'
        self._insert_data = data
        return self

    def update(self, data):
        self._operation = 'update'
        self._update_data = data
        return self

    def delete(self):
        self._operation = 'delete'
        return self

    def _matches(self, row):
        return all(f(row) for f in self.filters)

    def execute(self):
        rows = self.rows_store.get(self.table_name, [])

        if self._operation == 'insert':
            items = self._insert_data if isinstance(self._insert_data, list) else [self._insert_data]
            inserted = []
            for item in items:
                rec = copy.deepcopy(item)
                if 'id' not in rec or not rec['id']:
                    rec['id'] = str(uuid.uuid4())
                rows.append(rec)
                inserted.append(rec)
            self.rows_store[self.table_name] = rows
            res_data = inserted if isinstance(self._insert_data, list) else inserted[0]
            return MockResponse(res_data if self._is_single else inserted, count=len(inserted))

        filtered = [copy.deepcopy(r) for r in rows if self._matches(r)]

        if self._operation == 'update':
            updated = []
            for r in rows:
                if self._matches(r):
                    r.update(copy.deepcopy(self._update_data))
                    updated.append(copy.deepcopy(r))
            return MockResponse(updated[0] if (self._is_single and updated) else updated, count=len(updated))

        if self._operation == 'delete':
            remaining = [r for r in rows if not self._matches(r)]
            deleted_count = len(rows) - len(remaining)
            self.rows_store[self.table_name] = remaining
            return MockResponse([], count=deleted_count)

        # Select
        if self._order_col:
            filtered.sort(
                key=lambda x: (x.get(self._order_col) is None, x.get(self._order_col)),
                reverse=self._order_desc
            )

        total_count = len(filtered)
        if self._limit is not None:
            filtered = filtered[:self._limit]

        if self._is_single:
            single_val = filtered[0] if filtered else None
            return MockResponse(single_val, count=1 if single_val else 0)

        return MockResponse(filtered, count=total_count if self._count_exact else len(filtered))


class MockRpcBuilder:
    def __init__(self, fn_name, params):
        self.fn_name = fn_name
        self.params = params

    def execute(self):
        return MockResponse({'success': True, 'rpc': self.fn_name, 'params': self.params})


class MockAuth:
    def __init__(self):
        self.current_user = None

    def sign_out(self):
        self.current_user = None
        return True

    def set_session(self, access_token, refresh_token):
        return True

    def refresh_session(self, refresh_token):
        class MockSessionObj:
            access_token = 'new_access_mock'
            refresh_token = 'new_refresh_mock'
        class MockSessionResp:
            session = MockSessionObj()
        return MockSessionResp()


class MockSupabaseClient:
    def __init__(self, initial_tables=None):
        self.tables = copy.deepcopy(initial_tables) if initial_tables else {}
        self.auth = MockAuth()

    def table(self, table_name):
        return MockQueryBuilder(table_name, self.tables)

    def rpc(self, fn_name, params=None):
        return MockRpcBuilder(fn_name, params or {})
