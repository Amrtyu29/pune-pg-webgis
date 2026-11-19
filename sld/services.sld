<?xml version="1.0" encoding="UTF-8"?>
<!--
  Rule-based style for the "services" layer (PGs and hostels in and around Prabhag 11).
  Three rules, evaluated per feature with OGC filters:
    1. no name tag            -> hollow grey circle   (data-quality flag, see Q3)
    2. named, type = pg       -> orange circle
    3. named, hostel / guest_house -> blue circle
  Points outside the ward (inside_area = false) are drawn smaller and paler by a fourth rule.
  Written for GeoServer (SLD 1.0.0 with the GeoServer vendor options for labels).
-->
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>services</Name>
    <UserStyle>
      <Title>PGs and hostels: named vs unnamed, by type</Title>
      <FeatureTypeStyle>

        <Rule>
          <Name>unnamed</Name>
          <Title>No name in OSM</Title>
          <ogc:Filter>
            <ogc:PropertyIsNull><ogc:PropertyName>name</ogc:PropertyName></ogc:PropertyIsNull>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>circle</WellKnownName>
                <Fill><CssParameter name="fill">#ffffff</CssParameter></Fill>
                <Stroke><CssParameter name="stroke">#6b6b6b</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke>
              </Mark>
              <Size>11</Size>
            </Graphic>
          </PointSymbolizer>
        </Rule>

        <Rule>
          <Name>pg</Name>
          <Title>PG (paying guest), named</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:Not><ogc:PropertyIsNull><ogc:PropertyName>name</ogc:PropertyName></ogc:PropertyIsNull></ogc:Not>
              <ogc:PropertyIsEqualTo><ogc:PropertyName>service_type</ogc:PropertyName><ogc:Literal>pg</ogc:Literal></ogc:PropertyIsEqualTo>
            </ogc:And>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>circle</WellKnownName>
                <Fill><CssParameter name="fill">#e6550d</CssParameter></Fill>
                <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">1</CssParameter></Stroke>
              </Mark>
              <Size>12</Size>
            </Graphic>
          </PointSymbolizer>
          <TextSymbolizer>
            <Label><ogc:PropertyName>name</ogc:PropertyName></Label>
            <Font><CssParameter name="font-family">Arial</CssParameter><CssParameter name="font-size">10</CssParameter></Font>
            <LabelPlacement><PointPlacement><Displacement><DisplacementX>8</DisplacementX><DisplacementY>0</DisplacementY></Displacement></PointPlacement></LabelPlacement>
            <Halo><Radius>1.5</Radius><Fill><CssParameter name="fill">#ffffff</CssParameter></Fill></Halo>
            <Fill><CssParameter name="fill">#333333</CssParameter></Fill>
            <VendorOption name="conflictResolution">true</VendorOption>
            <VendorOption name="autoWrap">80</VendorOption>
          </TextSymbolizer>
        </Rule>

        <Rule>
          <Name>hostel</Name>
          <Title>Hostel or guest house, named</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:Not><ogc:PropertyIsNull><ogc:PropertyName>name</ogc:PropertyName></ogc:PropertyIsNull></ogc:Not>
              <ogc:PropertyIsNotEqualTo><ogc:PropertyName>service_type</ogc:PropertyName><ogc:Literal>pg</ogc:Literal></ogc:PropertyIsNotEqualTo>
            </ogc:And>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>circle</WellKnownName>
                <Fill><CssParameter name="fill">#3182bd</CssParameter></Fill>
                <Stroke><CssParameter name="stroke">#ffffff</CssParameter><CssParameter name="stroke-width">1</CssParameter></Stroke>
              </Mark>
              <Size>12</Size>
            </Graphic>
          </PointSymbolizer>
          <TextSymbolizer>
            <Label><ogc:PropertyName>name</ogc:PropertyName></Label>
            <Font><CssParameter name="font-family">Arial</CssParameter><CssParameter name="font-size">10</CssParameter></Font>
            <LabelPlacement><PointPlacement><Displacement><DisplacementX>8</DisplacementX><DisplacementY>0</DisplacementY></Displacement></PointPlacement></LabelPlacement>
            <Halo><Radius>1.5</Radius><Fill><CssParameter name="fill">#ffffff</CssParameter></Fill></Halo>
            <Fill><CssParameter name="fill">#333333</CssParameter></Fill>
            <VendorOption name="conflictResolution">true</VendorOption>
            <VendorOption name="autoWrap">80</VendorOption>
          </TextSymbolizer>
        </Rule>

      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
