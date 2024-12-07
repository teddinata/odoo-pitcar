/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount } from "@odoo/owl";

export class MapWidget extends Component {
    static template = "pitcar_custom.MapWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.map = null;
        this.marker = null;
        this.circle = null;

        onMounted(() => this.initMap());
        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
        });
    }

    async initMap() {
        try {
            if (!this.props.record) return;

            const mapElement = document.getElementById('map');
            if (!mapElement) {
                console.error('Map container not found');
                return;
            }

            const defaultLat = this.props.record.data.latitude || -6.2088;
            const defaultLng = this.props.record.data.longitude || 106.8456;
            const radius = this.props.record.data.radius || 100;

            // Initialize map
            this.map = L.map(mapElement).setView([defaultLat, defaultLng], 13);

            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(this.map);

            // Add draggable marker
            this.marker = L.marker([defaultLat, defaultLng], {
                draggable: true
            }).addTo(this.map);

            // Add radius circle
            this.circle = L.circle([defaultLat, defaultLng], {
                radius: radius,
                color: '#3388ff',
                fillOpacity: 0.2
            }).addTo(this.map);

            // Handle marker drag
            this.marker.on('dragend', (event) => {
                const pos = event.target.getLatLng();
                this.updateLocation(pos.lat, pos.lng);
            });

            // Force map to update its size
            setTimeout(() => {
                this.map.invalidateSize();
            }, 100);

        } catch (error) {
            console.error('Error initializing map:', error);
        }
    }

    updateLocation(lat, lng) {
        if (!this.props.record) return;
        
        this.props.record.update({
            latitude: lat,
            longitude: lng
        });
        
        if (this.circle) {
            this.circle.setLatLng([lat, lng]);
        }
    }
}

registry.category("fields").add("map", MapWidget);