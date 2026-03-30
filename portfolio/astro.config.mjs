import { defineConfig } from 'astro/config';

export default defineConfig({
  base: '/mlb-winforecaster',
  output: 'static',
  build: {
    assets: '_assets',
  },
});
