module.exports = {
  input: 'http://localhost:8866/openapi.json',
  output: './src/api',
  client: 'axios',
  name: 'BenchFinderApi',
  useOptions: true,
  useUnionTypes: true,
  exportCore: true,
  exportServices: true,
  exportModels: true,
  exportSchemas: false,
  indent: '  ',
  postfixServices: 'Service',
  postfixModels: '',
  request: './core/request.ts'
};
