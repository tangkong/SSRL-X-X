""" 
scans for high throughput stage
"""

from .locs import loc177
from ..devices.stages import s_stage
from ..devices.dexela import dexDet
from ..devices.misc_devices import shutter as fs

import time 
import matplotlib.pyplot as plt
import bluesky.plans as bp
import bluesky.plan_stubs as bps
from ssrltools.plans import meshcirc, nscan, level_stage_single

__all__ = ['loc177scan', 'dark_light_plan', 'expTimePlan', 'gather_plot_ims',
            'plot_dark_corrected', 'multi_run', ]

# scan sample locations
def loc177scan(dets, md={}):
    """loc177scan measures saved locations for a 177 pt 
    hitp library
    """
    # format locations and stage motors

    yield from bp.list_scan(dets, s_stage.px, list(loc177[0]), 
                                s_stage.py, list(loc177[1]))


# collection plans
# Basic dark > light collection plan
def dark_light_plan(dets=[dexDet], shutter=fs, md={}):
    '''
        Simple acquisition plan:
        - Close shutter, take image, open shutter, take image, close shutter
        dets : detectors to read from
        motors : motors to take readings from (not fully implemented yet)
        fs : Fast shutter, high is closed
        sample_name : the sample name
        Example usage:
        >>> RE(dark_light_plan())
    '''

    start_time = time.time()
    uids = []

    #yield from bps.sleep(1)

    #close fast shutter, take a dark
    yield from bps.mv(fs, 1)
    mdd = md.copy()
    mdd.update(name='dark')
    uid = yield from bp.count(dets, md=mdd)
    uids.append(uid)


    # open fast shutter, take light
    yield from bps.mv(fs, 0)
    mdl = md.copy()
    mdl.update(name='primary')
    uid = yield from bp.count(dets, md=mdl)
    uids.append(uid)

    end_time = time.time()
    print(f'Duration: {end_time - start_time:.3f} sec')
    return(uids)


# Plan for meshgrid + dark/light?...

# image time series
def expTimePlan(det, timeList=[1]):
    '''
    Run count with each exposure time in time list.  
    Specific to Dexela Detector, only run with single detector
    return uids from each count
    '''
    uids = []
    for time in timeList:
        # set acquire time
        yield from bps.mov(det.cam.acquire_time, time)
        uid = yield from bp.count([det], md=dict(acquire_time=time))

        yield from bps.sleep(1)
        uids.append(uid)
   
    return uids

#helper functions, probably should go in a separate file

import datetime
fts = datetime.datetime.fromtimestamp
def gather_plot_ims(hdrs):
    '''
    helper function for plotting images. 
    '''
    plots=[]
    times=[]
    # gather arrs from db
    for hdr in hdrs:
        arr = hdr.table(fill=True)['dexela_image'][1]
        plots.append(arr)
        time = hdr.start['time']
        times.append(time)
        

    global curr_pos
    curr_pos = 0
    # Register key event
    def key_event(e): 
        global curr_pos 
        if e.key == 'right': 
            curr_pos=curr_pos + 1 
        elif e.key == 'left': 
            curr_pos = curr_pos - 1  
        else: 
            return 
        curr_pos = curr_pos % len(plots) 
        ax.cla()
        curr_arr = plots[curr_pos]
        ax.imshow(curr_arr, vmax=curr_arr.mean() + 3*curr_arr.std()) 

        dt = fts(times[curr_pos])
        ax.set_title(f'{dt.month}/{dt.day}, {dt.hour}:{dt.minute}')
        fig.canvas.draw() 

    fig = plt.figure()
    fig.canvas.mpl_connect('key_press_event', key_event)
    ax = fig.add_subplot(111)
    ax.imshow(plots[0], vmax=plots[0].mean() + 3*plots[0].std())
    dt = fts(times[0])
    ax.set_title(f'{dt.month}/{dt.day}, {dt.hour}:{dt.minute}')

    plt.show()


def plot_dark_corrected(hdrs):
    '''
    looks for name='dark' or 'primary'
    otherwise assumes dark comes first?
    '''

    for hdr in hdrs:
        if hdr.start['name']=='dark':
            darkarr = hdr.table(fill=True)['dexela_image'][1]
        elif hdr.start['name'] == 'primary':
            lightarr = hdr.table(fill=True)['dexela_image'][1]
        else:
            print('mislabeled data... ignoring for now')
            return

    bkgd_subbed = lightarr.astype(int) - darkarr.astype(int)
    bkgd_subbed[ bkgd_subbed < 0 ] = 0
    plt.imshow(bkgd_subbed, vmax = bkgd_subbed.mean() + 3*bkgd_subbed.std())

def plot_MCA(hdrs):
    '''Plot MCA's from given hdr
    '''
    plt.figure()
    data = hdrs.table(fill=True)['xsp3_channel1'][1]

    plt.plot(data)
    plt.xlabel('Energy (keV)')
    plt.ylabel('Total counts')

def multi_run(acq_time, reps): 
    yield from bps.mv(dexDet.cam.acquire_time, acq_time) 
    print(dexDet.cam.acquire_time.read()) 
    yield from bps.mv(fs, 1) 
    dark_uid = yield from bp.count([dexDet], md={'name':'dark'}) 
    yield from bps.mv(fs, 0) 
    light_uids = [] 
    
    for _ in range(reps): 
        light_uid = yield from bp.count([dexDet], md={'name':'primary'}) 
        light_uids.append(light_uid) 
    
    return (dark_uid, light_uids) 