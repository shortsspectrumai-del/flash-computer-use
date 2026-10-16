"""Read-only OS accessibility snapshot. Also runnable by a system Python."""
from collections import deque
import json
import platform
import time


def linux_snapshot():
    import pyatspi
    desktop=pyatspi.Registry.getDesktop(0)
    active=[]
    for app in desktop:
        for window in app:
            try:
                if window.getState().contains(pyatspi.STATE_ACTIVE):
                    active.append((app,window))
            except Exception:
                continue
    if len(active)!=1:
        return {'available':True,'elements':[],'reason':'no_unique_active_window'}
    app,window=active[0]
    window_id=str(app.get_process_id())+'/'+str(window.path)
    elements=[]
    queue=deque([(window,'0')])
    deadline=time.monotonic()+.6
    visited=0
    while queue and visited<1500 and time.monotonic()<deadline:
        node,path=queue.popleft()
        visited+=1
        try:
            state=node.getState()
            if not state.contains(pyatspi.STATE_SHOWING):
                continue
            role=node.getRoleName()
            editable=state.contains(pyatspi.STATE_EDITABLE)
            is_canvas=role in {'canvas','drawing area','image','viewport','document frame'}
            interactive=editable or is_canvas or role in {'push button','toggle button','check box','radio button','menu item','page tab','combo box','link','list item','tree item'}
            if interactive and state.contains(pyatspi.STATE_ENABLED) and (node.name or is_canvas):
                r=node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
                if r.width>0 and r.height>0:
                    label=(node.name or role)[:160]
                    elements.append({'id':str(node.path),'label':label,'aliases':[label],'box':[r.x,r.y,r.width,r.height],'editable':editable,'role':role,'window':window_id})
            for i in range(min(node.childCount,150)):
                queue.append((node[i],path+'/'+str(i)))
        except Exception:
            continue
    return {'available':True,'window':window_id,'elements':elements[:625]}


def windows_snapshot():
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
    from pywinauto import Desktop
    handle=ctypes.windll.user32.GetForegroundWindow()
    root=Desktop(backend='uia').window(handle=handle).wrapper_object()
    elements=[]
    for control in root.descendants()[:1500]:
        try:
            info=control.element_info
            ctype=info.control_type
            is_canvas=ctype in {'Image','Document','Pane','Custom'}
            if not control.is_visible() or not control.is_enabled() or (not is_canvas and ctype not in {'Button','Edit','CheckBox','RadioButton','MenuItem','TabItem','ComboBox','Hyperlink','ListItem','TreeItem'}):
                continue
            rect=control.rectangle()
            if (not info.name and not is_canvas) or rect.width()<=0 or rect.height()<=0:
                continue
            label=(info.name or ctype)[:160]
            elements.append({'id':str(info.runtime_id),'label':label,'aliases':[label],'box':[rect.left,rect.top,rect.width(),rect.height()],
                             'editable':ctype=='Edit','role':ctype.lower(),'window':str(handle)})
        except Exception:
            continue
    return {'available':True,'window':str(handle),'elements':elements[:625]}


def mac_snapshot():
    import ApplicationServices as AX
    from AppKit import NSWorkspace
    if not AX.AXIsProcessTrusted():
        return {'available':False,'reason':'accessibility_permission_required','elements':[]}
    app=NSWorkspace.sharedWorkspace().frontmostApplication()
    pid=app.processIdentifier()
    application=AX.AXUIElementCreateApplication(pid)
    def attr(node,name):
        error,value=AX.AXUIElementCopyAttributeValue(node,name,None)
        return value if error==0 else None
    window=attr(application,'AXFocusedWindow')
    if window is None:
        return {'available':True,'elements':[]}
    window_id=str(pid)+'/'+str(attr(window,'AXTitle'))
    queue=deque([(window,'0')])
    elements=[]
    deadline=time.monotonic()+.6
    visited=0
    while queue and visited<1500 and time.monotonic()<deadline:
        node,path=queue.popleft()
        visited+=1
        role=attr(node,'AXRole')
        label=attr(node,'AXTitle') or attr(node,'AXDescription')
        is_canvas=role in {'AXImage','AXScrollArea','AXLayoutArea'}
        if (is_canvas or (role in {'AXButton','AXCheckBox','AXRadioButton','AXTextField','AXTextArea','AXComboBox','AXPopUpButton','AXLink'} and label)) and attr(node,'AXEnabled') is not False:
            p=attr(node,'AXPosition');s=attr(node,'AXSize')
            if p is not None and s is not None:
                okp,point=AX.AXValueGetValue(p,AX.kAXValueCGPointType,None)
                oks,size=AX.AXValueGetValue(s,AX.kAXValueCGSizeType,None)
                if okp and oks and size.width>0 and size.height>0:
                    lbl=str(label or role)[:160]
                    elements.append({'id':path,'label':lbl,'aliases':[lbl],'box':[round(point.x),round(point.y),round(size.width),round(size.height)],
                                     'editable':role in {'AXTextField','AXTextArea'},'role':str(role).lower(),'window':window_id})
        for i,child in enumerate((attr(node,'AXChildren') or [])[:150]):
            queue.append((child,path+'/'+str(i)))
    return {'available':True,'window':window_id,'elements':elements[:625]}


def main():
    try:
        adapter={'Linux':linux_snapshot,'Windows':windows_snapshot,'Darwin':mac_snapshot}.get(platform.system())
        result=adapter() if adapter else {'available':False,'reason':'unsupported_os','elements':[]}
    except Exception as exc:
        result={'available':False,'reason':type(exc).__name__,'elements':[]}
    print(json.dumps(result))


if __name__=='__main__':
    main()
