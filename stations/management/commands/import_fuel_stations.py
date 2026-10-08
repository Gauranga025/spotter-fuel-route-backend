import logging
import time
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.core.management.base import BaseCommand

from stations.models import FuelStation, GeocodeCache
from stations.services.geocoding import GeocodingService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import fuel stations from CSV file with geocoding'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            type=str,
            help='Path to the CSV file'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process per batch'
        )
        parser.add_argument(
            '--skip-geocoding',
            action='store_true',
            help='Skip geocoding (useful for testing)'
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry geocoding for stations with failed status'
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        batch_size = options['batch_size']
        skip_geocoding = options['skip_geocoding']
        retry_failed = options['retry_failed']

        self.stdout.write(
            self.style.SUCCESS(f'Starting import from {csv_path}')
        )

        # Read and validate CSV
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Failed to read CSV: {e}')
            )
            return

        # Validate required columns
        required_columns = [
            'OPIS Truckstop ID',
            'Truckstop Name',
            'Address',
            'City',
            'State',
            'Rack ID',
            'Retail Price'
        ]
        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            self.stderr.write(
                self.style.ERROR(
                    f'Missing required columns: {missing_columns}'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Found {len(df)} records in CSV'
            )
        )

        # Initialize geocoding service
        geocoding_service = GeocodingService()

        # Process in batches
        total_imported = 0
        total_updated = 0
        total_failed = 0

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size]
            self.stdout.write(
                f'Processing batch {i // batch_size + 1} '
                f'({len(batch)} records)...'
            )

            imported, updated, failed = self.process_batch(
                batch,
                geocoding_service,
                skip_geocoding,
                retry_failed
            )

            total_imported += imported
            total_updated += updated
            total_failed += failed

            # Rate limiting for geocoding
            if not skip_geocoding:
                time.sleep(1)

        self.stdout.write(
            self.style.SUCCESS(
                f'Import complete: {total_imported} imported, '
                f'{total_updated} updated, {total_failed} failed'
            )
        )

    def process_batch(
        self, batch, geocoding_service, skip_geocoding, retry_failed
    ):
        imported = 0
        updated = 0
        failed = 0

        for _, row in batch.iterrows():
            try:
                result = self.process_row(
                    row,
                    geocoding_service,
                    skip_geocoding,
                    retry_failed
                )
                if result == 'imported':
                    imported += 1
                elif result == 'updated':
                    updated += 1
                elif result == 'failed':
                    failed += 1
            except Exception as e:
                logger.error(f'Error processing row: {e}')
                failed += 1

        return imported, updated, failed

    def process_row(
        self, row, geocoding_service, skip_geocoding, retry_failed
    ):
        opis_id = int(row['OPIS Truckstop ID'])
        name = str(row['Truckstop Name']).strip()
        address = str(row['Address']).strip() if pd.notna(
            row['Address']
        ) else ''
        city = str(row['City']).strip()
        state = self.normalize_state(str(row['State']).strip())
        rack_id = int(row['Rack ID']) if pd.notna(row['Rack ID']) else None
        price_str = str(row['Retail Price']).strip()

        # Validate and parse price
        try:
            price = Decimal(price_str)
            if price < 0:
                raise ValueError('Price cannot be negative')
        except (InvalidOperation, ValueError) as e:
            logger.error(
                f'Invalid price for {name}: {price_str} - {e}'
            )
            return 'failed'

        # Check if station already exists
        station, created = FuelStation.objects.get_or_create(
            opis_truckstop_id=opis_id,
            defaults={
                'truckstop_name': name,
                'address': address,
                'city': city,
                'state': state,
                'rack_id': rack_id,
                'retail_price': price,
            }
        )

        if not created:
            # Update existing station
            station.truckstop_name = name
            station.address = address
            station.city = city
            station.state = state
            station.rack_id = rack_id
            station.retail_price = price
            station.save(update_fields=[
                'truckstop_name', 'address', 'city',
                'state', 'rack_id', 'retail_price'
            ])

        # Geocode if needed
        should_geocode = False
        if not skip_geocoding:
            if station.geocode_status == 'pending':
                should_geocode = True
            elif retry_failed and station.geocode_status == 'failed':
                should_geocode = True

        if should_geocode:
            self.geocode_station(station, geocoding_service)

        return 'imported' if created else 'updated'

    def normalize_state(self, state):
        """Normalize state code to uppercase 2-letter format."""
        state = state.upper()
        if len(state) == 2:
            return state
        # Could add state name to code mapping here if needed
        return state

    def geocode_station(self, station, geocoding_service):
        """Geocode a single station with caching."""
        # Build address key for caching
        address_parts = [station.address, station.city, station.state]
        address_key = ', '.join(filter(None, address_parts))

        # Check cache first
        cached = GeocodeCache.objects.filter(
            address_key=address_key
        ).first()

        if cached:
            self.apply_cached_coordinates(station, cached)
            return

        # Geocode
        try:
            result = geocoding_service.geocode(address_key)
            if result:
                station.location = result['point']
                station.geocode_status = 'success'
                station.geocode_precision = result['precision']
                station.save()

                # Cache the result
                GeocodeCache.objects.create(
                    address_key=address_key,
                    latitude=Decimal(str(result['latitude'])),
                    longitude=Decimal(str(result['longitude'])),
                    precision=result['precision']
                )
            else:
                # Try fallback to city-level
                city_key = f'{station.city}, {station.state}, USA'
                city_cached = GeocodeCache.objects.filter(
                    address_key=city_key
                ).first()

                if city_cached:
                    self.apply_cached_coordinates(station, city_cached)
                    station.geocode_status = 'fallback'
                else:
                    city_result = geocoding_service.geocode(city_key)
                    if city_result:
                        station.location = city_result['point']
                        station.geocode_status = 'fallback'
                        station.geocode_precision = city_result['precision']
                        station.save()

                        GeocodeCache.objects.create(
                            address_key=city_key,
                            latitude=Decimal(str(city_result['latitude'])),
                            longitude=Decimal(str(city_result['longitude'])),
                            precision=city_result['precision']
                        )
                    else:
                        station.geocode_status = 'failed'
                        station.save()
        except Exception as e:
            logger.error(f'Geocoding failed for {station}: {e}')
            station.geocode_status = 'failed'
            station.save()

    def apply_cached_coordinates(self, station, cache_entry):
        """Apply cached coordinates to station."""
        from django.contrib.gis.geos import Point

        station.location = Point(
            float(cache_entry.longitude),
            float(cache_entry.latitude)
        )
        station.geocode_status = 'success'
        station.geocode_precision = cache_entry.precision
        station.save()
