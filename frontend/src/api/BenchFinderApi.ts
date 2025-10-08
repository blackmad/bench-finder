/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BaseHttpRequest } from './core/BaseHttpRequest';
import type { OpenAPIConfig } from './core/OpenAPI';
import { AxiosHttpRequest } from './core/AxiosHttpRequest';
import { BenchesService } from './services/BenchesService';
import { ConfigService } from './services/ConfigService';
import { ImagesService } from './services/ImagesService';
import { MapillaryService } from './services/MapillaryService';
import { ReportingService } from './services/ReportingService';
import { SearchService } from './services/SearchService';
import { StatisticsService } from './services/StatisticsService';
type HttpRequestConstructor = new (config: OpenAPIConfig) => BaseHttpRequest;
export class BenchFinderApi {
    public readonly benches: BenchesService;
    public readonly config: ConfigService;
    public readonly images: ImagesService;
    public readonly mapillary: MapillaryService;
    public readonly reporting: ReportingService;
    public readonly search: SearchService;
    public readonly statistics: StatisticsService;
    public readonly request: BaseHttpRequest;
    constructor(config?: Partial<OpenAPIConfig>, HttpRequest: HttpRequestConstructor = AxiosHttpRequest) {
        this.request = new HttpRequest({
            BASE: config?.BASE ?? '',
            VERSION: config?.VERSION ?? '2.0.0',
            WITH_CREDENTIALS: config?.WITH_CREDENTIALS ?? false,
            CREDENTIALS: config?.CREDENTIALS ?? 'include',
            TOKEN: config?.TOKEN,
            USERNAME: config?.USERNAME,
            PASSWORD: config?.PASSWORD,
            HEADERS: config?.HEADERS,
            ENCODE_PATH: config?.ENCODE_PATH,
        });
        this.benches = new BenchesService(this.request);
        this.config = new ConfigService(this.request);
        this.images = new ImagesService(this.request);
        this.mapillary = new MapillaryService(this.request);
        this.reporting = new ReportingService(this.request);
        this.search = new SearchService(this.request);
        this.statistics = new StatisticsService(this.request);
    }
}

