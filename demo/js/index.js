import mixinCitiesDataSource from './CitiesDataSource.js'

const defaultImageryProviders = Cesium.createDefaultImageryProviderViewModels();

const esriWorldImagery = defaultImageryProviders.find(p => p.name === 'ESRI World Imagery');

const viewer = new Cesium.Viewer('viewer', {
    selectedImageryProviderViewModel: esriWorldImagery,
    imageryProviderViewModels: defaultImageryProviders
});

mixinCitiesDataSource(viewer);
