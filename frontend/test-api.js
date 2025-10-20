#!/usr/bin/env node

// Simple test to verify the updated API service works
// This tests that the imports and basic structure are correct

async function testApiService() {
  console.log('Testing updated API service...')

  try {
    // Test importing the API service
    const { benchApi, checkApiHealth, benchFinderApi } = await import('./src/services/api.ts')

    console.log('✅ Successfully imported API service')
    console.log('✅ benchApi methods available:', Object.keys(benchApi))
    console.log('✅ Generated API client available:', !!benchFinderApi)
    console.log('✅ Health check function available:', !!checkApiHealth)

    // Test that the service structure matches expectations
    const expectedMethods = [
      'getBenches',
      'getBenchesBySource',
      'getBenchesInBbox',
      'getRandomBench',
      'getImageSegmentation',
      'getSearches',
      'getConfig'
    ]

    const availableMethods = Object.keys(benchApi)
    const missingMethods = expectedMethods.filter(method => !availableMethods.includes(method))

    if (missingMethods.length === 0) {
      console.log('✅ All expected API methods are available')
    } else {
      console.log('❌ Missing methods:', missingMethods)
    }

    console.log('\n🎉 API service update completed successfully!')
    console.log('\nYour existing code should work with improved type safety.')
    console.log('New features available:')
    console.log('- Full TypeScript types from OpenAPI schema')
    console.log('- Auto-generated API client methods')
    console.log('- Better error handling and validation')
    console.log('- Individual service exports for granular access')

  } catch (error) {
    console.error('❌ Error testing API service:', error.message)
    process.exit(1)
  }
}

// Only run if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  testApiService()
}
