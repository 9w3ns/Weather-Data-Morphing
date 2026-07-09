#! python 3
import Rhino.Geometry as rg

Flat_Numbers = [1.0, 2.0, 3.0]
Nested_Numbers = [[1.0, 2.0], [3.0], [4.0, 5.0, 6.0]]
Point_Tuples = [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 2.0, 0.0)]
Rhino_Points = [rg.Point3d(0, 0, 0), rg.Point3d(1, 1, 0), rg.Point3d(2, 2, 0)]
Report = "Script ran to completion."
