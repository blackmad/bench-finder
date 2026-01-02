# Firestore Migration Status

## Completed ✅

1. **Firestore Database Service** (`bench_finder/services/firestore_database.py`)
   - Created complete Firestore database service
   - Mapped all SQLModel models to Firestore collections
   - Implemented all core database operations (CRUD)
   - Handles integer IDs (stored as strings in Firestore documents)

2. **Database Service Wrapper** (`bench_finder/services/database.py`)
   - Updated `BenchDatabase` to use Firestore instead of SQLAlchemy
   - Maintains backward compatibility with existing API
   - All methods now delegate to FirestoreDatabase

3. **API Database Service** (`api/database_service.py`)
   - Updated to use Firestore queries
   - Rewrote `get_search_results()` and `get_benches_with_detections()` to use Firestore

## In Progress 🔄

4. **FastAPI Server** (`api/fastapi_server.py`)
   - **Status**: Partially updated
   - **Issue**: Contains 61 SQL query usages that need to be converted to Firestore
   - **Complexity**: Many queries use complex SQL features (joins, aggregations, subqueries) that need to be rewritten
   - **Next Steps**: 
     - Update endpoints incrementally
     - Replace `session.query()` with Firestore queries
     - Handle complex queries by fetching data in multiple steps (Firestore doesn't support joins)

## Remaining Work 📋

### High Priority
- [ ] Update all FastAPI endpoints to use Firestore queries
- [ ] Update CLI tools that use `BenchDatabase`
- [ ] Update other services that use SQLAlchemy queries directly
- [ ] Test all endpoints to ensure they work with Firestore

### Medium Priority
- [ ] Add Firestore indexes for common query patterns
- [ ] Optimize queries to reduce Firestore read operations
- [ ] Add pagination support where needed (Firestore has built-in pagination)

### Low Priority
- [ ] Remove SQLAlchemy dependencies from `pyproject.toml`
- [ ] Update documentation
- [ ] Create migration script to move data from CloudSQL to Firestore

## Key Differences: SQLAlchemy vs Firestore

### Limitations
- **No Joins**: Firestore doesn't support SQL joins. Need to fetch related data in separate queries
- **Limited Aggregations**: Firestore has limited aggregation functions. Complex aggregations need to be done in application code
- **No Transactions Across Collections**: Firestore transactions are limited to a single collection
- **Query Limitations**: 
  - Can only filter on one field with inequality operators
  - Can't do `IN` queries with multiple values (need separate queries)
  - Can't do complex `OR` queries easily

### Advantages
- **Cost**: Much cheaper than CloudSQL for read-heavy workloads
- **Scalability**: Automatically scales
- **Real-time**: Built-in real-time updates
- **Serverless**: No connection pooling needed

## Migration Strategy

1. **Phase 1** (Current): Core database operations ✅
2. **Phase 2**: Update FastAPI endpoints (in progress)
3. **Phase 3**: Update CLI and tools
4. **Phase 4**: Data migration from CloudSQL to Firestore
5. **Phase 5**: Remove SQLAlchemy dependencies

## Testing

To test the Firestore migration:

1. Ensure Firebase credentials are configured:
   ```bash
   export FIREBASE_CREDENTIALS_PATH=path/to/firebase_creds.json
   # OR
   export FIREBASE_CREDENTIALS_BASE64=base64_encoded_credentials
   ```

2. Test basic operations:
   ```python
   from bench_finder.services.database import BenchDatabase
   
   db = BenchDatabase()
   # Test operations...
   ```

3. Test API endpoints (after updating FastAPI server)

## Notes

- Firestore document IDs are stored as strings, but we maintain integer IDs in the document data for compatibility
- Timestamps are handled automatically by Firestore's `SERVER_TIMESTAMP`
- Complex queries may need to be broken into multiple Firestore queries and combined in application code

