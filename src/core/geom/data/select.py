from ...base import *
from .transform import SelectionTransformBase


class GeomSelectionBase(BaseObject):

    def __editstate__(self, state):

        del state["_poly_selection_data"]
        del state["_selected_subobj_ids"]

    def __setstate__(self, state):

        self._poly_selection_data = {"selected": [], "unselected": []}
        self._selected_subobj_ids = {"vert": [], "edge": [], "poly": [], "normal": []}

    def __init__(self):

        self._poly_selection_data = {"selected": [], "unselected": []}
        self._selected_subobj_ids = {"vert": [], "edge": [], "poly": [], "normal": []}
        self._sel_subobj_ids_backup = {}
        self._selection_backup = {}
        self._tmp_geom_pickable = None
        self._tmp_geom_sel_state = None
        self._tmp_row_indices = {}

    def update_selection(self, subobj_type, subobjs_to_select, subobjs_to_deselect,
                         update_verts_to_transf=True, selection_colors=None):

        selected_subobj_ids = self._selected_subobj_ids[subobj_type]
        geoms = self._geoms[subobj_type]
        selected_subobjs = [subobj for subobj in subobjs_to_select
                            if subobj.get_id() not in selected_subobj_ids]
        deselected_subobjs = [subobj for subobj in subobjs_to_deselect
                              if subobj.get_id() in selected_subobj_ids]

        if not (selected_subobjs or deselected_subobjs):
            return False

        if subobj_type == "poly":

            geom_selected = geoms["selected"]
            geom_unselected = geoms["unselected"]
            sel_data = self._poly_selection_data
            data_selected = sel_data["selected"]
            data_unselected = sel_data["unselected"]
            prim = geom_selected.node().modify_geom(0).modify_primitive(0)
            array = prim.modify_vertices()
            stride = array.get_array_format().get_stride()
            handle_sel = array.modify_handle()
            prim = geom_unselected.node().modify_geom(0).modify_primitive(0)
            handle_unsel = prim.modify_vertices().modify_handle()
            row_ranges_sel = []
            row_ranges_unsel = []

            for poly in selected_subobjs:
                selected_subobj_ids.append(poly.get_id())
                start = data_unselected.index(poly[0]) * 3
                size = len(poly)
                row_ranges_unsel.append((start, size, poly))

            for poly in deselected_subobjs:
                selected_subobj_ids.remove(poly.get_id())
                start = data_selected.index(poly[0]) * 3
                size = len(poly)
                row_ranges_sel.append((start, size, poly))

            row_ranges_sel.sort(reverse=True)
            row_ranges_unsel.sort(reverse=True)
            subdata_sel = ""
            subdata_unsel = ""

            for start, size, poly in row_ranges_unsel:

                for vert_ids in poly:
                    data_unselected.remove(vert_ids)

                data_selected.extend(poly)

                subdata_unsel += handle_unsel.get_subdata(start * stride, size * stride)
                handle_unsel.set_subdata(start * stride, size * stride, "")

            handle_sel.set_data(handle_sel.get_data() + subdata_unsel)

            for start, size, poly in row_ranges_sel:

                for vert_ids in poly:
                    data_selected.remove(vert_ids)

                data_unselected.extend(poly)

                subdata_sel += handle_sel.get_subdata(start * stride, size * stride)
                handle_sel.set_subdata(start * stride, size * stride, "")

            handle_unsel.set_data(handle_unsel.get_data() + subdata_sel)

        else:

            if subobj_type == "vert":
                combined_subobjs = self._merged_verts
            elif subobj_type == "edge":
                combined_subobjs = self._merged_edges
            elif subobj_type == "normal":
                combined_subobjs = self._shared_normals

            selected_subobjs = set(combined_subobjs[subobj.get_id()] for subobj in selected_subobjs)
            deselected_subobjs = set(combined_subobjs[subobj.get_id()] for subobj in deselected_subobjs)

            sel_state_geom = geoms["sel_state"]
            vertex_data = sel_state_geom.node().modify_geom(0).modify_vertex_data()
            col_writer = GeomVertexWriter(vertex_data, "color")

            if selection_colors:
                sel_colors = selection_colors
            else:
                sel_colors = Mgr.get("subobj_selection_colors")[subobj_type]

            color_sel = sel_colors["selected"]
            color_unsel = sel_colors["unselected"]

            for combined_subobj in selected_subobjs:

                selected_subobj_ids.extend(combined_subobj)

                for row_index in combined_subobj.get_row_indices():
                    col_writer.set_row(row_index)
                    col_writer.set_data4f(color_sel)

            for combined_subobj in deselected_subobjs:

                for subobj_id in combined_subobj:
                    selected_subobj_ids.remove(subobj_id)

                for row_index in combined_subobj.get_row_indices():
                    col_writer.set_row(row_index)
                    col_writer.set_data4f(color_unsel)

            if subobj_type == "normal":

                selected_normal_ids = []
                deselected_normal_ids = []

                for combined_subobj in selected_subobjs:
                    selected_normal_ids.extend(combined_subobj)

                for combined_subobj in deselected_subobjs:
                    deselected_normal_ids.extend(combined_subobj)

                self.update_locked_normal_selection(selected_normal_ids, deselected_normal_ids)

        if update_verts_to_transf:
            self._update_verts_to_transform(subobj_type)

        return True

    def init_subobject_select(self, subobj_lvl):

        geoms = self._geoms

        if GlobalData["selection_via_poly"]:

            if GlobalData["active_transform_type"]:
                GlobalData["active_transform_type"] = ""
                Mgr.update_app("active_transform_type", "")
                Mgr.update_app("status", "select", "")

            self.create_selection_backup("poly")
            geoms["poly"]["selected"].set_state(Mgr.get("temp_poly_selection_state"))
            self.init_subobject_select_via_poly(subobj_lvl)

        else:

            render_masks = Mgr.get("render_masks")["all"]
            picking_masks = Mgr.get("picking_masks")["all"]
            geoms[subobj_lvl]["pickable"].show_through(picking_masks)
            geoms["poly"]["pickable"].show(picking_masks)
            geoms["poly"]["selected"].hide(render_masks)

            if not geoms["poly"]["unselected"].is_hidden(render_masks):
                geoms["poly"]["unselected"].hide(render_masks)
                geoms["top"].show(render_masks)

    def init_subobject_select_via_poly(self, subobj_type):

        self.clear_selection("poly", False)

        # clean up temporary vertex data
        if self._tmp_geom_pickable:
            self._tmp_geom_pickable.remove_node()
            self._tmp_geom_pickable = None
            self._tmp_geom_sel_state.remove_node()
            self._tmp_geom_sel_state = None
            self._tmp_row_indices = {}

        # Allow picking polys instead of the subobjects of the given type;
        # as soon as a poly is clicked, its subobjects (of the given type) become
        # pickable instead of polys.

        render_masks = Mgr.get("render_masks")["all"]
        picking_masks = Mgr.get("picking_masks")["all"]
        geoms = self._geoms
        geoms[subobj_type]["pickable"].hide(picking_masks)
        geoms["poly"]["pickable"].show_through(picking_masks)
        geoms["poly"]["selected"].show(render_masks)

        if not geoms["top"].is_hidden(render_masks):
            geoms["top"].hide(render_masks)
            geoms["poly"]["unselected"].show(render_masks)

    def subobject_select_via_poly(self, subobj_lvl, picked_poly):

        if subobj_lvl == "vert":
            self.vertex_select_via_poly(picked_poly)
        elif subobj_lvl == "edge":
            self.edge_select_via_poly(picked_poly)
        elif subobj_lvl == "normal":
            self.normal_select_via_poly(picked_poly)

    def select_temp_subobject(self, subobj_lvl, color_id):

        row = self._tmp_row_indices.get(color_id)

        if row is None:
            return False

        colors = Mgr.get("subobj_selection_colors")[subobj_lvl]
        geom = self._tmp_geom_sel_state.node().modify_geom(0)
        vertex_data = geom.get_vertex_data().set_color((.3, .3, .3, .5))
        geom.set_vertex_data(vertex_data)
        col_writer = GeomVertexWriter(geom.modify_vertex_data(), "color")
        col_writer.set_row(row)
        col_writer.set_data4f(colors["selected"])

        if subobj_lvl == "edge":
            col_writer.set_data4f(colors["selected"])

        return True

    def is_selected(self, subobj):

        return subobj.get_id() in self._selected_subobj_ids[subobj.get_type()]

    def get_selection(self, subobj_lvl):

        selected_subobj_ids = self._selected_subobj_ids[subobj_lvl]

        if subobj_lvl == "poly":
            polys = self._subobjs["poly"]
            return [polys[poly_id] for poly_id in selected_subobj_ids]

        if subobj_lvl == "vert":
            combined_subobjs = self._merged_verts
        elif subobj_lvl == "edge":
            combined_subobjs = self._merged_edges
        elif subobj_lvl == "normal":
            combined_subobjs = self._shared_normals

        return list(set(combined_subobjs[subobj_id] for subobj_id in selected_subobj_ids))

    def create_selection_backup(self, subobj_lvl):

        if subobj_lvl in self._selection_backup:
            return

        self._sel_subobj_ids_backup[subobj_lvl] = self._selected_subobj_ids[subobj_lvl][:]
        self._selection_backup[subobj_lvl] = self.get_selection(subobj_lvl)

    def restore_selection_backup(self, subobj_lvl):

        sel_backup = self._selection_backup

        if subobj_lvl not in sel_backup:
            return

        self.clear_selection(subobj_lvl, False)
        self.update_selection(subobj_lvl, sel_backup[subobj_lvl], [], False)
        del sel_backup[subobj_lvl]
        del self._sel_subobj_ids_backup[subobj_lvl]

    def remove_selection_backup(self, subobj_lvl):

        sel_backup = self._selection_backup

        if subobj_lvl in sel_backup:
            del sel_backup[subobj_lvl]
            del self._sel_subobj_ids_backup[subobj_lvl]

    def clear_selection(self, subobj_lvl, update_verts_to_transf=True, force=False):

        if not (force or self._selected_subobj_ids[subobj_lvl]):
            return

        geoms = self._geoms[subobj_lvl]

        if subobj_lvl == "poly":

            geom_selected = geoms["selected"]
            geom_unselected = geoms["unselected"]
            sel_data = self._poly_selection_data
            sel_data["unselected"].extend(sel_data["selected"])
            sel_data["selected"] = []
            handle = geom_selected.node().modify_geom(0).modify_primitive(0).modify_vertices().modify_handle()
            data = handle.get_data()
            handle.set_data("")
            handle = geom_unselected.node().modify_geom(0).modify_primitive(0).modify_vertices().modify_handle()
            handle.set_data(handle.get_data() + data)

        elif subobj_lvl == "normal":

            color = Mgr.get("subobj_selection_colors")["normal"]["unselected"]
            color_locked = Mgr.get("subobj_selection_colors")["normal"]["locked_unsel"]
            vertex_data = geoms["sel_state"].node().modify_geom(0).modify_vertex_data()
            col_writer = GeomVertexWriter(vertex_data, "color")
            verts = self._subobjs["vert"]

            for vert_id in self._selected_subobj_ids["normal"]:
                vert = verts[vert_id]
                row = vert.get_row_index()
                col = color_locked if vert.has_locked_normal() else color
                col_writer.set_row(row)
                col_writer.set_data4f(col)

        else:

            vertex_data = geoms["sel_state"].node().modify_geom(0).modify_vertex_data()
            color = Mgr.get("subobj_selection_colors")[subobj_lvl]["unselected"]
            new_data = vertex_data.set_color(color)
            vertex_data.set_array(1, new_data.get_array(1))

        self._selected_subobj_ids[subobj_lvl] = []

        if update_verts_to_transf:
            self._verts_to_transf[subobj_lvl] = {}

    def delete_selection(self, subobj_lvl):

        subobjs = self._subobjs
        verts = subobjs["vert"]
        edges = subobjs["edge"]
        polys = subobjs["poly"]
        ordered_polys = self._ordered_polys

        selected_subobj_ids = self._selected_subobj_ids
        selected_vert_ids = selected_subobj_ids["vert"]
        selected_edge_ids = selected_subobj_ids["edge"]
        selected_poly_ids = selected_subobj_ids["poly"]
        selected_normal_ids = selected_subobj_ids["normal"]
        self._verts_to_transf["vert"] = {}
        self._verts_to_transf["edge"] = {}
        self._verts_to_transf["poly"] = {}
        verts_to_delete = []
        edges_to_delete = []
        border_edges = []

        if subobj_lvl == "vert":

            polys_to_delete = set()

            for vert in (verts[v_id] for v_id in selected_vert_ids):
                polys_to_delete.add(polys[vert.get_polygon_id()])

        elif subobj_lvl == "edge":

            polys_to_delete = set()

            for edge in (edges[e_id] for e_id in selected_edge_ids):
                polys_to_delete.add(polys[edge.get_polygon_id()])

        elif subobj_lvl == "poly":

            polys_to_delete = [polys[poly_id] for poly_id in selected_poly_ids]

        poly_index = min(ordered_polys.index(poly) for poly in polys_to_delete)
        polys_to_offset = ordered_polys[poly_index:]

        row_ranges_to_delete = []
        merged_verts = self._merged_verts
        merged_edges = self._merged_edges
        shared_normals = self._shared_normals

        subobjs_to_unreg = self._subobjs_to_unreg = {"vert": {}, "edge": {}, "poly": {}}

        subobj_change = self._subobj_change
        subobj_change["vert"]["deleted"] = vert_change = {}
        subobj_change["edge"]["deleted"] = edge_change = {}
        subobj_change["poly"]["deleted"] = poly_change = {}

        for poly in polys_to_delete:

            poly_verts = poly.get_vertices()
            vert = poly_verts[0]
            row = vert.get_row_index()
            row_ranges_to_delete.append((row, len(poly_verts)))

            verts_to_delete.extend(poly_verts)
            edges_to_delete.extend(poly.get_edges())

            for edge_id in poly.get_edge_ids():

                merged_edge = merged_edges[edge_id]

                if merged_edge in border_edges:
                    border_edges.remove(merged_edge)
                else:
                    border_edges.append(merged_edge)

            ordered_polys.remove(poly)
            poly_id = poly.get_id()
            subobjs_to_unreg["poly"][poly_id] = poly
            poly_change[poly] = poly.get_creation_time()

            if poly_id in selected_poly_ids:
                selected_poly_ids.remove(poly_id)

        merged_verts_to_resmooth = set()

        for vert in verts_to_delete:

            vert_id = vert.get_id()
            subobjs_to_unreg["vert"][vert_id] = vert
            vert_change[vert] = vert.get_creation_time()

            if vert_id in selected_vert_ids:
                selected_vert_ids.remove(vert_id)

            if vert_id in selected_normal_ids:
                selected_normal_ids.remove(vert_id)

            if vert_id in merged_verts:
                merged_vert = merged_verts[vert_id]
                merged_vert.remove(vert_id)
                del merged_verts[vert_id]
                merged_verts_to_resmooth.add(merged_vert)

            if vert_id in shared_normals:
                shared_normal = shared_normals[vert_id]
                shared_normal.discard(vert_id)
                del shared_normals[vert_id]

        sel_data = self._poly_selection_data
        geoms = self._geoms

        for state in ("selected", "unselected"):
            sel_data[state] = []
            prim = geoms["poly"][state].node().modify_geom(0).modify_primitive(0)
            prim.modify_vertices().modify_handle().set_data("")
            # NOTE: do *NOT* call prim.clearVertices(), as this will explicitly
            # remove all data from the primitive, and adding new data through
            # prim.modify_vertices().modify_handle().set_data(data) will not
            # internally notify Panda3D that the primitive has now been updated
            # to contain new data. This will result in an assertion error later on.

        for edge in edges_to_delete:

            edge_id = edge.get_id()
            subobjs_to_unreg["edge"][edge_id] = edge
            edge_change[edge] = edge.get_creation_time()

            if edge_id in selected_edge_ids:
                selected_edge_ids.remove(edge_id)

            if edge_id in merged_edges:

                merged_edge = merged_edges[edge_id]
                merged_edge.remove(edge_id)
                del merged_edges[edge_id]

                if not merged_edge[:] and merged_edge in border_edges:
                    border_edges.remove(merged_edge)

        if border_edges:

            new_merged_verts = self.fix_borders(border_edges)

            if new_merged_verts:
                self.update_normal_sharing(new_merged_verts)
                merged_verts_to_resmooth.update(new_merged_verts)

        self.unregister(locally=True)

        row_index_offset = 0

        for poly in polys_to_offset:

            if poly in polys_to_delete:
                row_index_offset -= poly.get_vertex_count()
                continue

            poly_verts = poly.get_vertices()

            for vert in poly_verts:
                vert.offset_row_index(row_index_offset)

        row_ranges_to_delete.sort(reverse=True)

        vert_geom = geoms["vert"]["pickable"].node().modify_geom(0)
        edge_geom = geoms["edge"]["pickable"].node().modify_geom(0)
        normal_geom = geoms["normal"]["pickable"].node().modify_geom(0)
        vertex_data_vert = vert_geom.modify_vertex_data()
        vertex_data_edge = edge_geom.modify_vertex_data()
        vertex_data_normal = normal_geom.modify_vertex_data()
        vertex_data_poly = self._vertex_data["poly"]
        vertex_data_poly_picking = self._vertex_data["poly_picking"]

        vert_array = vertex_data_vert.modify_array(1)
        vert_handle = vert_array.modify_handle()
        vert_stride = vert_array.get_array_format().get_stride()
        edge_array = vertex_data_edge.modify_array(1)
        edge_handle = edge_array.modify_handle()
        edge_stride = edge_array.get_array_format().get_stride()
        picking_array = vertex_data_poly_picking.modify_array(1)
        picking_handle = picking_array.modify_handle()
        picking_stride = picking_array.get_array_format().get_stride()

        poly_arrays = []
        poly_handles = []
        poly_strides = []

        for i in range(vertex_data_poly.get_num_arrays()):
            poly_array = vertex_data_poly.modify_array(i)
            poly_arrays.append(poly_array)
            poly_handles.append(poly_array.modify_handle())
            poly_strides.append(poly_array.get_array_format().get_stride())

        pos_array = poly_arrays[0]

        count = self._data_row_count

        for start, size in row_ranges_to_delete:

            vert_handle.set_subdata(start * vert_stride, size * vert_stride, "")
            edge_handle.set_subdata((start + count) * edge_stride, size * edge_stride, "")
            edge_handle.set_subdata(start * edge_stride, size * edge_stride, "")
            picking_handle.set_subdata(start * picking_stride, size * picking_stride, "")

            for poly_handle, poly_stride in zip(poly_handles, poly_strides):
                poly_handle.set_subdata(start * poly_stride, size * poly_stride, "")

            count -= size

        self._data_row_count = count = len(verts)
        sel_colors = Mgr.get("subobj_selection_colors")

        vertex_data_vert.set_num_rows(count)
        vertex_data_vert.set_array(0, GeomVertexArrayData(pos_array))
        vertex_data_normal.set_num_rows(count)
        vertex_data_poly_picking.set_array(0, GeomVertexArrayData(pos_array))
        vertex_data_normal.set_array(0, GeomVertexArrayData(pos_array))
        vertex_data_normal.set_array(1, GeomVertexArrayData(vert_array))
        vertex_data_normal.set_array(2, GeomVertexArrayData(poly_arrays[2]))

        vertex_data_vert = geoms["vert"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data_vert.set_num_rows(count)
        vertex_data_vert.set_array(0, GeomVertexArrayData(pos_array))
        new_data = vertex_data_vert.set_color(sel_colors["vert"]["unselected"])
        vertex_data_vert.set_array(1, new_data.get_array(1))

        vertex_data_normal = geoms["normal"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data_normal.set_num_rows(count)
        vertex_data_normal.set_array(0, GeomVertexArrayData(pos_array))
        new_data = vertex_data_normal.set_color(sel_colors["normal"]["unselected"])
        vertex_data_normal.set_array(1, new_data.get_array(1))
        vertex_data_normal.set_array(2, GeomVertexArrayData(poly_arrays[2]))

        tmp_array = GeomVertexArrayData(pos_array)
        handle = tmp_array.modify_handle()
        handle.set_data(handle.get_data() * 2)
        vertex_data_edge.set_num_rows(count * 2)
        vertex_data_edge.set_array(0, tmp_array)

        vertex_data_edge = geoms["edge"]["sel_state"].node().modify_geom(0).modify_vertex_data()
        vertex_data_edge.set_num_rows(count * 2)
        vertex_data_edge.set_array(0, GeomVertexArrayData(tmp_array))
        new_data = vertex_data_edge.set_color(sel_colors["edge"]["unselected"])
        vertex_data_edge.set_array(1, new_data.get_array(1))

        data_unselected = sel_data["unselected"]

        for poly in ordered_polys:
            data_unselected.extend(poly)

        points_prim = GeomPoints(Geom.UH_static)
        points_prim.reserve_num_vertices(count)
        points_prim.add_next_vertices(count)
        vert_geom.set_primitive(0, points_prim)
        normal_geom.set_primitive(0, GeomPoints(points_prim))
        geom_node = geoms["vert"]["sel_state"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomPoints(points_prim))
        geom_node = geoms["normal"]["sel_state"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomPoints(points_prim))

        lines_prim = GeomLines(Geom.UH_static)
        lines_prim.reserve_num_vertices(count * 2)

        tris_prim = GeomTriangles(Geom.UH_static)

        for poly in ordered_polys:

            for edge in poly.get_edges():
                row1, row2 = edge.get_row_indices()
                lines_prim.add_vertices(row1, row2)

            for vert_ids in poly:
                tris_prim.add_vertices(*[verts[v_id].get_row_index() for v_id in vert_ids])

        edge_geom.set_primitive(0, lines_prim)
        geom_node = geoms["edge"]["sel_state"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomLines(lines_prim))

        geom_node_top = self._toplvl_node
        geom_node_top.modify_geom(0).set_primitive(0, tris_prim)

        geom_node = geoms["poly"]["unselected"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomTriangles(tris_prim))

        geom_node = geoms["poly"]["pickable"].node()
        geom_node.modify_geom(0).set_primitive(0, GeomTriangles(tris_prim))

        vertex_data_top = geom_node_top.modify_geom(0).modify_vertex_data()

        for i, poly_array in enumerate(poly_arrays):
            vertex_data_top.set_array(i, poly_array)

        geom_node.modify_geom(0).set_primitive(0, GeomTriangles(tris_prim))

        for subobj_type in ("vert", "edge", "poly", "normal"):
            selected_subobj_ids[subobj_type] = []

        if selected_vert_ids:
            selected_verts = (verts[vert_id] for vert_id in selected_vert_ids)
            self.update_selection("vert", selected_verts, [])

        if selected_edge_ids:
            selected_edges = (edges[edge_id] for edge_id in selected_edge_ids)
            self.update_selection("edge", selected_edges, [])

        if selected_poly_ids:
            selected_polys = (polys[poly_id] for poly_id in selected_poly_ids)
            self.update_selection("poly", selected_polys, [])

        if selected_normal_ids:
            selected_normals = (shared_normals[normal_id] for normal_id in selected_normal_ids)
            self.update_selection("normal", selected_normals, [])

        poly_ids = [poly.get_id() for poly in polys_to_delete]
        self.smooth_polygons(poly_ids, smooth=False, update_normals=False)
        self._normal_sharing_change = True
        self.update_vertex_normals(merged_verts_to_resmooth)
        self.get_toplevel_object().get_bbox().update(*self._origin.get_tight_bounds())

    def _restore_subobj_selection(self, time_id):

        obj_id = self.get_toplevel_object().get_id()
        prop_id = self._unique_prop_ids["subobj_selection"]
        data = Mgr.do("load_last_from_history", obj_id, prop_id, time_id)

        verts = self._subobjs["vert"]
        normal_ids = data["normal"]
        old_sel_normal_ids = set(self._selected_subobj_ids["normal"])
        new_sel_normal_ids = set(normal_ids)
        sel_normal_ids = new_sel_normal_ids - old_sel_normal_ids
        unsel_normal_ids = old_sel_normal_ids - new_sel_normal_ids
        unsel_normal_ids.intersection_update(verts)
        shared_normals = self._shared_normals
        original_shared_normals = {}

        if unsel_normal_ids:
            tmp_shared_normal = Mgr.do("create_shared_normal", self, unsel_normal_ids)
            unsel_id = tmp_shared_normal.get_id()
            original_shared_normals[unsel_id] = shared_normals[unsel_id]
            shared_normals[unsel_id] = tmp_shared_normal
            unsel_normals = [tmp_shared_normal]
        else:
            unsel_normals = []

        if sel_normal_ids:
            tmp_shared_normal = Mgr.do("create_shared_normal", self, sel_normal_ids)
            sel_id = tmp_shared_normal.get_id()
            original_shared_normals[sel_id] = shared_normals[sel_id]
            shared_normals[sel_id] = tmp_shared_normal
            sel_normals = [tmp_shared_normal]
        else:
            sel_normals = []

        self.update_selection("normal", sel_normals, unsel_normals, False)

        if unsel_normals:
            shared_normals[unsel_id] = original_shared_normals[unsel_id]
        if sel_normals:
            shared_normals[sel_id] = original_shared_normals[sel_id]

        self._update_verts_to_transform("normal")

        for subobj_type in ("vert", "edge", "poly"):

            subobjs = self._subobjs[subobj_type]

            subobj_ids = data[subobj_type]
            old_sel_subobj_ids = set(self._selected_subobj_ids[subobj_type])
            new_sel_subobj_ids = set(subobj_ids)
            sel_subobj_ids = new_sel_subobj_ids - old_sel_subobj_ids
            unsel_subobj_ids = old_sel_subobj_ids - new_sel_subobj_ids
            unsel_subobj_ids.intersection_update(subobjs)

            unsel_subobjs = [subobjs[i] for i in unsel_subobj_ids]
            sel_subobjs = [subobjs[i] for i in sel_subobj_ids]

            if subobj_type in ("vert", "edge"):

                merged_subobjs = self._merged_verts if subobj_type == "vert" else self._merged_edges
                original_merged_subobjs = {}

                if unsel_subobjs:

                    tmp_merged_subobj = Mgr.do("create_merged_%s" % subobj_type, self)

                    for subobj_id in unsel_subobj_ids:
                        tmp_merged_subobj.append(subobj_id)

                    unsel_id = tmp_merged_subobj.get_id()
                    original_merged_subobjs[unsel_id] = merged_subobjs[unsel_id]
                    merged_subobjs[unsel_id] = tmp_merged_subobj
                    unsel_subobjs = [subobjs[unsel_id]]

                if sel_subobjs:

                    tmp_merged_subobj = Mgr.do("create_merged_%s" % subobj_type, self)

                    for subobj_id in sel_subobj_ids:
                        tmp_merged_subobj.append(subobj_id)

                    sel_id = tmp_merged_subobj.get_id()
                    original_merged_subobjs[sel_id] = merged_subobjs[sel_id]
                    merged_subobjs[sel_id] = tmp_merged_subobj
                    sel_subobjs = [subobjs[sel_id]]

            self.update_selection(subobj_type, sel_subobjs, unsel_subobjs, False)

            if subobj_type in ("vert", "edge"):
                if unsel_subobjs:
                    merged_subobjs[unsel_id] = original_merged_subobjs[unsel_id]
                if sel_subobjs:
                    merged_subobjs[sel_id] = original_merged_subobjs[sel_id]

            self._update_verts_to_transform(subobj_type)


class Selection(SelectionTransformBase):

    def __init__(self, obj_level, subobjs):

        SelectionTransformBase.__init__(self)

        self._objs = subobjs
        self._obj_level = obj_level

        self._groups = {}

        for obj in subobjs:
            self._groups.setdefault(obj.get_geom_data_object(), []).append(obj)

    def __getitem__(self, index):

        try:
            return self._objs[index]
        except IndexError:
            raise IndexError("Index out of range.")
        except TypeError:
            raise TypeError("Index must be an integer value.")

    def __len__(self):

        return len(self._objs)

    def get_toplevel_objects(self, get_group=False):

        return [geom_data_obj.get_toplevel_object(get_group) for geom_data_obj in self._groups]

    def get_toplevel_object(self, get_group=False):
        """ Return a random top-level object """

        if self._groups:
            return self._groups.keys()[0].get_toplevel_object(get_group)

    def update(self):

        self.update_center_pos()
        self.update_ui()

    def add(self, subobj, add_to_hist=True):

        sel = self._objs
        old_sel = set(sel)
        sel_to_add = set(subobj.get_special_selection())
        common = old_sel & sel_to_add

        if common:
            sel_to_add -= common

        if not sel_to_add:
            return False

        geom_data_objs = {}
        groups = self._groups

        for obj in sel_to_add:
            geom_data_obj = obj.get_geom_data_object()
            geom_data_objs.setdefault(geom_data_obj, []).append(obj)
            groups.setdefault(geom_data_obj, []).append(obj)

        for geom_data_obj, objs in geom_data_objs.iteritems():
            geom_data_obj.update_selection(self._obj_level, objs, [])

        sel.extend(sel_to_add)

        task = lambda: Mgr.get("selection").update()
        PendingTasks.add(task, "update_selection", "ui")

        if add_to_hist:

            subobj_descr = {"vert": "vertex", "edge": "edge", "poly": "polygon", "normal": "normal"}
            event_descr = 'Add to %s selection' % subobj_descr[self._obj_level]
            obj_data = {}
            event_data = {"objects": obj_data}

            for geom_data_obj in geom_data_objs:
                obj = geom_data_obj.get_toplevel_object()
                obj_data[obj.get_id()] = geom_data_obj.get_data_to_store("prop_change", "subobj_selection")

            # make undo/redoable
            Mgr.do("add_history", event_descr, event_data)

        return True

    def remove(self, subobj, add_to_hist=True):

        sel = self._objs
        old_sel = set(sel)
        sel_to_remove = set(subobj.get_special_selection())
        common = old_sel & sel_to_remove

        if not common:
            return False

        geom_data_objs = {}
        groups = self._groups

        for obj in common:

            sel.remove(obj)
            geom_data_obj = obj.get_geom_data_object()
            geom_data_objs.setdefault(geom_data_obj, []).append(obj)

            groups[geom_data_obj].remove(obj)

            if not groups[geom_data_obj]:
                del groups[geom_data_obj]

        for geom_data_obj, objs in geom_data_objs.iteritems():
            geom_data_obj.update_selection(self._obj_level, [], objs)

        task = lambda: Mgr.get("selection").update()
        PendingTasks.add(task, "update_selection", "ui")

        if add_to_hist:

            subobj_descr = {"vert": "vertex", "edge": "edge", "poly": "polygon", "normal": "normal"}
            event_descr = 'Remove from %s selection' % subobj_descr[self._obj_level]
            obj_data = {}
            event_data = {"objects": obj_data}

            for geom_data_obj in geom_data_objs:
                obj = geom_data_obj.get_toplevel_object()
                obj_data[obj.get_id()] = geom_data_obj.get_data_to_store("prop_change", "subobj_selection")

            # make undo/redoable
            Mgr.do("add_history", event_descr, event_data)

        return True

    def replace(self, subobj, add_to_hist=True):

        sel = self._objs
        old_sel = set(sel)
        new_sel = set(subobj.get_special_selection())
        common = old_sel & new_sel

        if common:
            old_sel -= common
            new_sel -= common

        if not (old_sel or new_sel):
            return False

        geom_data_objs = {}

        for old_obj in old_sel:
            sel.remove(old_obj)
            geom_data_obj = old_obj.get_geom_data_object()
            geom_data_objs.setdefault(geom_data_obj, {"sel": [], "desel": []})["desel"].append(old_obj)

        for new_obj in new_sel:
            geom_data_obj = new_obj.get_geom_data_object()
            geom_data_objs.setdefault(geom_data_obj, {"sel": [], "desel": []})["sel"].append(new_obj)

        for geom_data_obj, objs in geom_data_objs.iteritems():
            geom_data_obj.update_selection(self._obj_level, objs["sel"], objs["desel"])

        sel.extend(new_sel)

        self._groups = groups = {}

        for obj in common | new_sel:
            groups.setdefault(obj.get_geom_data_object(), []).append(obj)

        task = lambda: Mgr.get("selection").update()
        PendingTasks.add(task, "update_selection", "ui")

        if add_to_hist and geom_data_objs:

            subobj_descr = {"vert": "vertex", "edge": "edge", "poly": "polygon", "normal": "normal"}
            event_descr = 'Replace %s selection' % subobj_descr[self._obj_level]
            obj_data = {}
            event_data = {"objects": obj_data}

            for geom_data_obj in geom_data_objs:
                obj = geom_data_obj.get_toplevel_object()
                obj_data[obj.get_id()] = geom_data_obj.get_data_to_store("prop_change", "subobj_selection")

            # make undo/redoable
            Mgr.do("add_history", event_descr, event_data)

        return True

    def clear(self, add_to_hist=True):

        if not self._objs:
            return False

        obj_lvl = self._obj_level
        geom_data_objs = []

        for geom_data_obj in self._groups:
            geom_data_obj.clear_selection(obj_lvl)
            geom_data_objs.append(geom_data_obj)

        self._groups = {}
        self._objs = []

        task = lambda: Mgr.get("selection").update()
        PendingTasks.add(task, "update_selection", "ui")

        if add_to_hist:

            subobj_descr = {"vert": "vertex", "edge": "edge", "poly": "polygon", "normal": "normal"}
            event_descr = 'Clear %s selection' % subobj_descr[obj_lvl]
            obj_data = {}
            event_data = {"objects": obj_data}

            for geom_data_obj in geom_data_objs:
                obj = geom_data_obj.get_toplevel_object()
                obj_data[obj.get_id()] = geom_data_obj.get_data_to_store("prop_change", "subobj_selection")

            # make undo/redoable
            Mgr.do("add_history", event_descr, event_data)

        return True

    def delete(self, add_to_hist=True):

        obj_lvl = self._obj_level

        if obj_lvl == "normal":
            return False

        if not self._objs:
            return False

        geom_data_objs = self._groups.keys()

        self._groups = {}
        self._objs = []

        task = lambda: Mgr.get("selection").update()
        PendingTasks.add(task, "update_selection", "ui")

        for geom_data_obj in geom_data_objs:
            geom_data_obj.delete_selection(obj_lvl)

        if add_to_hist:

            Mgr.do("update_history_time")

            subobj_descr = {"vert": "vertex", "edge": "edge", "poly": "polygon", "normal": "normal"}
            event_descr = 'Delete %s selection' % subobj_descr[obj_lvl]
            obj_data = {}
            event_data = {"objects": obj_data}

            for geom_data_obj in geom_data_objs:
                obj = geom_data_obj.get_toplevel_object()
                obj_data[obj.get_id()] = geom_data_obj.get_data_to_store("subobj_change")

            # make undo/redoable
            Mgr.do("add_history", event_descr, event_data, update_time_id=False)

        return True


# subobject selection manager
class SelectionManager(BaseObject):

    def __init__(self):

        self._color_id = None
        self._selections = {}
        self._prev_obj_lvl = None

        # the following variables are used to select a subobject using its polygon
        self._picked_poly = None
        self._tmp_color_id = None
        self._toggle_select = False
        self._pixel_under_mouse = VBase4()

        np = NodePath("poly_sel_state")
        poly_sel_state_off = np.get_state()
        tex_stage = TextureStage("poly_selection")
        tex_stage.set_sort(100)
        tex_stage.set_priority(-1)
        tex_stage.set_mode(TextureStage.M_add)
        np.set_transparency(TransparencyAttrib.M_none)
        np.set_tex_gen(tex_stage, RenderAttrib.M_world_position)
        np.set_tex_projector(tex_stage, self.world, self.cam())
        tex = Texture()
        tex.read(Filename(GFX_PATH + "sel_tex.png"))
        np.set_texture(tex_stage, tex)
        np.set_tex_scale(tex_stage, 100.)
        red = VBase4(1., 0., 0., 1.)
        material = Material("poly_selection")
        material.set_diffuse(red)
        material.set_emission(red * .3)
        np.set_material(material)
        poly_sel_state = np.get_state()
        poly_sel_effects = np.get_effects()
        green = VBase4(0., 1., 0., 1.)
        material = Material("temp_poly_selection")
        material.set_diffuse(green)
        material.set_emission(green * .3)
        np.set_material(material)
        tmp_poly_sel_state = np.get_state()
        Mgr.expose("poly_selection_state_off", lambda: poly_sel_state_off)
        Mgr.expose("poly_selection_state", lambda: poly_sel_state)
        Mgr.expose("poly_selection_effects", lambda: poly_sel_effects)
        Mgr.expose("temp_poly_selection_state", lambda: tmp_poly_sel_state)

        GlobalData.set_default("selection_via_poly", False)

        vert_colors = {"selected": (1., 0., 0., 1.), "unselected": (.5, .5, 1., 1.)}
        edge_colors = {"selected": (1., 0., 0., 1.), "unselected": (1., 1., 1., 1.)}
        normal_colors = {"selected": (1., 0.3, 0.3, 1.), "unselected": (.75, .75, 0., 1.),
                         "locked_sel": (0.75, 0.3, 1., 1.), "locked_unsel": (0.3, 0.5, 1., 1.)}
        subobj_sel_colors = {"vert": vert_colors, "edge": edge_colors, "normal": normal_colors}

        Mgr.expose("subobj_selection_colors", lambda: subobj_sel_colors)

        Mgr.expose("selection_vert", lambda: self._selections["vert"])
        Mgr.expose("selection_edge", lambda: self._selections["edge"])
        Mgr.expose("selection_poly", lambda: self._selections["poly"])
        Mgr.expose("selection_normal", lambda: self._selections["normal"])
        Mgr.accept("update_selection_vert", lambda: self.__update_selection("vert"))
        Mgr.accept("update_selection_edge", lambda: self.__update_selection("edge"))
        Mgr.accept("update_selection_poly", lambda: self.__update_selection("poly"))
        Mgr.accept("update_selection_normal", lambda: self.__update_selection("normal"))
        Mgr.accept("select_vert", lambda *args: self.__select("vert", *args))
        Mgr.accept("select_edge", lambda *args: self.__select("edge", *args))
        Mgr.accept("select_poly", lambda *args: self.__select("poly", *args))
        Mgr.accept("select_normal", lambda *args: self.__select("normal", *args))
        Mgr.accept("select_single_vert", lambda: self.__select_single("vert"))
        Mgr.accept("select_single_edge", lambda: self.__select_single("edge"))
        Mgr.accept("select_single_poly", lambda: self.__select_single("poly"))
        Mgr.accept("select_single_normal", lambda: self.__select_single("normal"))
        Mgr.add_app_updater("active_obj_level", lambda: self.__clear_prev_selection(True))
        Mgr.add_app_updater("selection_via_poly", self.__set_subobject_select_via_poly)

        add_state = Mgr.add_state
        add_state("selection_via_poly", -1, self.__start_subobj_picking)

        bind = Mgr.bind_state
        bind("selection_via_poly", "select subobj",
             "mouse1-up", self.__select_subobj)
        bind("selection_via_poly", "cancel subobj selection",
             "mouse3-up", self.__cancel_select)

        status_data = GlobalData["status_data"]
        info = "LMB-drag over subobject to select it; RMB to cancel"
        status_data["selection_via_poly"] = {"mode": "Select subobject", "info": info}

    def __clear_prev_selection(self, check_top=False):

        obj_lvl = GlobalData["active_obj_level"]

        if check_top and obj_lvl != "top":
            return

        if self._prev_obj_lvl:
            self._selections[self._prev_obj_lvl] = None
            self._prev_obj_lvl = None

        selection = Mgr.get("selection", "top")
        sel_count = len(selection)
        obj = selection[0]
        geom_data_obj = obj.get_geom_object().get_geom_data_object()

        for prop_id in geom_data_obj.get_type_property_ids(obj_lvl):
            value = geom_data_obj.get_property(prop_id, for_remote_update=True, obj_lvl=obj_lvl)
            value = (value, sel_count)
            Mgr.update_remotely("selected_obj_prop", "editable_geom", prop_id, value)

    def __update_selection(self, obj_lvl):

        self.__clear_prev_selection()
        subobjs = []

        for obj in Mgr.get("selection", "top"):
            subobjs.extend(obj.get_subobj_selection(obj_lvl))

        self._selections[obj_lvl] = sel = Selection(obj_lvl, subobjs)
        sel.update()
        self._prev_obj_lvl = obj_lvl

    def __select(self, obj_lvl, picked_obj, toggle):

        if obj_lvl == "vert":
            if GlobalData["selection_via_poly"]:
                obj = picked_obj if picked_obj and picked_obj.get_type() == "poly" else None
                self._picked_poly = obj
            else:
                obj = picked_obj.get_merged_vertex() if picked_obj else None
        elif obj_lvl == "edge":
            if GlobalData["selection_via_poly"]:
                obj = picked_obj if picked_obj and picked_obj.get_type() == "poly" else None
                self._picked_poly = obj
            else:
                obj = picked_obj.get_merged_edge() if picked_obj else None
                if obj and GlobalData["subobj_edit_options"]["sel_edges_by_border"] and len(obj) > 1:
                    obj = None
        elif obj_lvl == "normal":
            if GlobalData["selection_via_poly"]:
                obj = picked_obj if picked_obj and picked_obj.get_type() == "poly" else None
                self._picked_poly = obj
            else:
                obj = picked_obj.get_shared_normal() if picked_obj else None
        elif obj_lvl == "poly":
            obj = picked_obj

        if self._picked_poly:
            self._toggle_select = toggle
            Mgr.enter_state("selection_via_poly")
            return False, False

        self._color_id = obj.get_picking_color_id() if obj else None

        if toggle:
            ret = self.__toggle_select(obj_lvl)
        else:
            ret = self.__default_select(obj_lvl)

        selection = self._selections[obj_lvl]

        if not (obj and obj in selection):
            obj = selection[0] if selection else None

        if obj:

            cs_type = GlobalData["coord_sys_type"]
            tc_type = GlobalData["transf_center_type"]
            toplvl_obj = obj.get_toplevel_object()

            if cs_type == "local":
                Mgr.update_locally("coord_sys", cs_type, toplvl_obj)

            if tc_type == "pivot":
                Mgr.update_locally("transf_center", tc_type, toplvl_obj)

        return ret

    def __default_select(self, obj_lvl):

        if obj_lvl == "normal":
            obj = Mgr.get("vert", self._color_id)
        else:
            obj = Mgr.get(obj_lvl, self._color_id)

        if obj_lvl == "vert":
            obj = obj.get_merged_vertex() if obj else None
        elif obj_lvl == "edge":
            obj = obj.get_merged_edge() if obj else None
        elif obj_lvl == "normal":
            obj = obj.get_shared_normal() if obj else None

        selection = self._selections[obj_lvl]
        can_select_single = False
        start_mouse_checking = False

        if obj:

            if GlobalData["active_transform_type"]:

                if obj in selection and len(selection) > 1:

                    # When the user clicks one of multiple selected objects, updating the
                    # selection must be delayed until it is clear whether he wants to
                    # transform the entire selection or simply have only this object
                    # selected (this is determined by checking if the mouse has moved at
                    # least a certain number of pixels by the time the left mouse button
                    # is released).

                    can_select_single = True

                else:

                    selection.replace(obj)

                start_mouse_checking = True

            else:

                selection.replace(obj)

        else:

            selection.clear()

        return can_select_single, start_mouse_checking

    def __select_single(self, obj_lvl):

        # If multiple objects were selected and no transformation occurred, a single
        # object has been selected out of that previous selection.

        if obj_lvl == "normal":
            obj = Mgr.get("vert", self._color_id)
        else:
            obj = Mgr.get(obj_lvl, self._color_id)

        if obj_lvl == "vert":
            obj = obj.get_merged_vertex() if obj else None
        elif obj_lvl == "edge":
            obj = obj.get_merged_edge() if obj else None
        elif obj_lvl == "normal":
            obj = obj.get_shared_normal() if obj else None

        self._selections[obj_lvl].replace(obj)

    def __toggle_select(self, obj_lvl):

        if obj_lvl == "normal":
            obj = Mgr.get("vert", self._color_id)
        else:
            obj = Mgr.get(obj_lvl, self._color_id)

        if obj_lvl == "vert":
            obj = obj.get_merged_vertex() if obj else None
        elif obj_lvl == "edge":
            obj = obj.get_merged_edge() if obj else None
        elif obj_lvl == "normal":
            obj = obj.get_shared_normal() if obj else None

        selection = self._selections[obj_lvl]
        start_mouse_checking = False

        if obj:

            if obj in selection:
                selection.remove(obj)
                transform_allowed = False
            else:
                selection.add(obj)
                transform_allowed = GlobalData["active_transform_type"]

            if transform_allowed:
                start_mouse_checking = True

        return False, start_mouse_checking

    def __set_subobject_select_via_poly(self, via_poly=False):

        if not via_poly:

            models = Mgr.get("model_objs")

            for model in models:
                if model.get_geom_type() == "editable_geom":
                    geom_data_obj = model.get_geom_object().get_geom_data_object()
                    geom_data_obj.restore_selection_backup("poly")

        obj_lvl = GlobalData["active_obj_level"]

        if obj_lvl not in ("vert", "edge", "normal"):
            return

        GlobalData["selection_via_poly"] = via_poly
        selection = Mgr.get("selection", "top")

        for obj in selection:
            obj.get_geom_object().get_geom_data_object().init_subobject_select(obj_lvl)

    def __start_subobj_picking(self, prev_state_id, is_active):

        Mgr.add_task(self.__pick_subobj, "pick_subobj")
        Mgr.remove_task("update_cursor")
        subobj_lvl = GlobalData["active_obj_level"]

        for model in Mgr.get("selection", "top"):
            geom_data_obj = model.get_geom_object().get_geom_data_object()
            geom_data_obj.subobject_select_via_poly(subobj_lvl, self._picked_poly)

        # temporarily select picked poly
        geom_data_obj = self._picked_poly.get_geom_data_object()
        geom_data_obj.update_selection("poly", [self._picked_poly], [], False)

        Mgr.update_app("status", "selection_via_poly")

        cs_type = GlobalData["coord_sys_type"]
        tc_type = GlobalData["transf_center_type"]
        toplvl_obj = self._picked_poly.get_toplevel_object()

        if cs_type == "local":
            Mgr.update_locally("coord_sys", cs_type, toplvl_obj)

        if tc_type == "pivot":
            Mgr.update_locally("transf_center", tc_type, toplvl_obj)

    def __pick_subobj(self, task):

        pixel_under_mouse = Mgr.get("pixel_under_mouse")

        if self._pixel_under_mouse != pixel_under_mouse:

            if pixel_under_mouse == VBase4():

                Mgr.set_cursor("main")

            else:

                Mgr.set_cursor("select")
                r, g, b, a = [int(round(c * 255.)) for c in pixel_under_mouse]
                color_id = r << 16 | g << 8 | b  # credit to coppertop @ panda3d.org
                geom_data_obj = self._picked_poly.get_geom_data_object()
                subobj_lvl = GlobalData["active_obj_level"]

                # temporarily select vertex
                if geom_data_obj.select_temp_subobject(subobj_lvl, color_id):
                    self._tmp_color_id = color_id

            self._pixel_under_mouse = pixel_under_mouse

        return task.cont

    def __select_subobj(self):

        Mgr.remove_task("pick_subobj")
        Mgr.enter_state("selection_mode")
        subobj_lvl = GlobalData["active_obj_level"]

        if self._tmp_color_id is None:

            obj = None

        else:

            geom_data_obj = self._picked_poly.get_geom_data_object()

            if subobj_lvl == "vert":
                vert_id = Mgr.get("vert", self._tmp_color_id).get_id()
                obj = geom_data_obj.get_merged_vertex(vert_id)
            elif subobj_lvl == "edge":
                edge_id = Mgr.get("edge", self._tmp_color_id).get_id()
                obj = geom_data_obj.get_merged_edge(edge_id)
                obj = (None if GlobalData["subobj_edit_options"]["sel_edges_by_border"]
                       and len(obj) > 1 else obj)
            elif subobj_lvl == "normal":
                vert_id = Mgr.get("vert", self._tmp_color_id).get_id()
                obj = geom_data_obj.get_shared_normal(vert_id)

        self._color_id = obj.get_picking_color_id() if obj else None

        if self._toggle_select:
            self.__toggle_select(subobj_lvl)
        else:
            self.__default_select(subobj_lvl)

        for model in Mgr.get("selection", "top"):
            geom_data_obj = model.get_geom_object().get_geom_data_object()
            geom_data_obj.init_subobject_select_via_poly(subobj_lvl)

        self._picked_poly = None
        self._tmp_color_id = None
        self._toggle_select = False
        self._pixel_under_mouse = VBase4()

    def __cancel_select(self):

        Mgr.remove_task("pick_subobj")
        Mgr.enter_state("selection_mode")
        subobj_lvl = GlobalData["active_obj_level"]

        for model in Mgr.get("selection", "top"):
            geom_data_obj = model.get_geom_object().get_geom_data_object()
            geom_data_obj.init_subobject_select_via_poly(subobj_lvl)

        self._picked_poly = None
        self._tmp_color_id = None
        self._toggle_select = False
        self._pixel_under_mouse = VBase4()


MainObjects.add_class(SelectionManager)
