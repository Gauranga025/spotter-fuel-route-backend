from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Load pre-geocoded fuel station fixture for testing'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Loading fuel station fixture...')
        )

        try:
            # Load the fixture
            call_command('loaddata', 'fuel_stations_fixture.json')

            self.stdout.write(
                self.style.SUCCESS(
                    'Fixture loaded successfully. '
                    'Use this for testing without geocoding.'
                )
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Failed to load fixture: {e}')
            )
            self.stderr.write(
                self.style.WARNING(
                    'To create the fixture, run: '
                    'python manage.py dumpdata stations.FuelStation '
                    '--indent 2 > stations/fixtures/'
                    'fuel_stations_fixture.json'
                )
            )
