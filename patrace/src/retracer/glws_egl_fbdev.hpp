#if !defined(GLWS_EGL_FBDEV_HPP)
#define GLWS_EGL_FBDEV_HPP

#include "retracer/glws_egl.hpp"

namespace retracer {
class GlwsEglFbdev : public GlwsEgl
{
public:
    GlwsEglFbdev();
    ~GlwsEglFbdev();

    virtual EGLImageKHR createImageKHR(Context* context, EGLenum target, uintptr_t buffer, const EGLint* attrib_list) override;
    virtual Drawable* CreateDrawable(int width, int height, int win, EGLint const* attribList);
    virtual bool steppable() override { return true; }
    virtual void processStepEvent() override;
};

}

#endif // !defined(GLWS_EGL_FBDEV_HPP)
