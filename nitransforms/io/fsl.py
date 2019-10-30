"""Read/write FSL's transforms."""
import numpy as np
from nibabel.affines import voxel_sizes

from .base import BaseLinearTransformList, LinearParameters


class FSLLinearTransform(LinearParameters):
    """A string-based structure for FSL linear transforms."""

    def __str__(self):
        """Generate a string representation."""
        lines = [' '.join(['%g' % col for col in row])
                 for row in self.structarr['parameters']]
        return '\n'.join(lines + [''])

    def to_string(self):
        """Convert to a string directly writeable to file."""
        return self.__str__()

    @classmethod
    def from_ras(cls, ras, moving, reference):
        """Create an ITK affine from a nitransform's RAS+ matrix."""
        # Adjust for reference image offset and orientation
        refswp, refspc = _fsl_aff_adapt(reference)
        pre = reference.affine.dot(
            np.linalg.inv(refspc).dot(np.linalg.inv(refswp)))

        # Adjust for moving image offset and orientation
        movswp, movspc = _fsl_aff_adapt(moving)
        post = np.linalg.inv(movswp).dot(movspc.dot(np.linalg.inv(
            moving.affine)))

        # Compose FSL transform
        mat = np.linalg.inv(
            np.swapaxes(post.dot(ras.dot(pre)), 0, 1))

        tf = cls()
        tf.structarr['parameters'] = mat.T
        return tf

    @classmethod
    def from_string(cls, string):
        """Read the struct from string."""
        tf = cls()
        sa = tf.structarr
        sa['parameters'] = np.genfromtxt(
            [string], dtype=cls.dtype['parameters'])
        return tf


class FSLLinearTransformArray(BaseLinearTransformList):
    """A string-based structure for series of FSL linear transforms."""

    _inner_type = FSLLinearTransform

    def to_filename(self, filename):
        """Store this transform to a file with the appropriate format."""
        if len(self.xforms) == 1:
            self.xforms[0].to_filename(filename)
            return

        for i, xfm in enumerate(self.xforms):
            with open('%s.%03d' % (filename, i), 'w') as f:
                f.write(xfm.to_string())

    def to_ras(self, moving, reference):
        """Return a nitransforms' internal RAS matrix."""
        return np.stack([xfm.to_ras(moving=moving, reference=reference)
                         for xfm in self.xforms])

    def to_string(self):
        """Convert to a string directly writeable to file."""
        return '\n\n'.join([xfm.to_string() for xfm in self.xforms])

    @classmethod
    def from_fileobj(cls, fileobj, check=True):
        """Read the struct from a file object."""
        return cls.from_string(fileobj.read())

    @classmethod
    def from_ras(cls, ras, moving, reference):
        """Create an ITK affine from a nitransform's RAS+ matrix."""
        _self = cls()
        _self.xforms = [cls._inner_type.from_ras(
            ras[i, ...], moving=moving, reference=reference)
            for i in range(ras.shape[0])]
        return _self

    @classmethod
    def from_string(cls, string):
        """Read the struct from string."""
        _self = cls()
        _self.xforms = [cls._inner_type.from_string(l.strip())
                        for l in string.splitlines() if l.strip()]
        return _self


def _fsl_aff_adapt(space):
    """
    Adapt FSL affines.

    Calculates a matrix to convert from the original RAS image
    coordinates to FSL's internal coordinate system of transforms
    """
    aff = space.affine
    zooms = list(voxel_sizes(aff)) + [1]
    swp = np.eye(4)
    if np.linalg.det(aff) > 0:
        swp[0, 0] = -1.0
        swp[0, 3] = (space.shape[0] - 1) * zooms[0]
    return swp, np.diag(zooms)
