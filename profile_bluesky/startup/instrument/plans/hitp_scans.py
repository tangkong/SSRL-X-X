""" 
scans for high throughput stage
"""

from .locs import loc177
from ..devices.stages import s_stage
from ..devices.xspress3 import xsp3
from ..devices.misc_devices import shutter as fs, lrf, I0, I1, table_busy, table_trigger
from ..framework import db

import time 
import matplotlib.pyplot as plt
import bluesky.plans as bp
from bluesky.preprocessors import inject_md_decorator 
import bluesky.plan_stubs as bps
from ssrltools.plans import meshcirc, nscan, level_stage_single

__all__ = ['loc_177_scan', 'loc_cust_scan', 'dark_light_plan', 'exp_time_plan', 'gather_plot_ims',
            'plot_dark_corrected', 'multi_acquire_plan', 'level_stage_single', ]

# scan sample locations
@inject_md_decorator({'macro_name': 'loc_177_scan'})
def loc_177_scan(dets, skip=0, md={}):
    """loc_177_scan scans across a library with 177 points, measuring each 
    detector in dets

    :param dets: detectors to be 
    :type dets: list
    :param skip: number of data points to skip
    :yield: things from list_scan
    :rtype: Msg
    """
    # format locations and stage motors
    if I0 not in dets:
        dets.append(I0)
    if I1 not in dets:
        dets.append(I1)

    if xsp3 in dets:
        yield from bps.mv(xsp3.total_points, 177)

    # inject logic via per_step 
    class stateful_per_step:
        
        def __init__(self, skip):
            self.skip = skip
            self.cnt = 0
            #print(self.skip, self.cnt)

        def __call__(self, detectors, step, pos_cache):
            """
            has signature of bps.one_and_step, but with added logic of skipping 
            a point if it is outside of provided radius
            """
            if self.cnt < self.skip: # if not enough skipped
                self.cnt += 1
                pass
            else:
                yield from bps.one_nd_step(detectors, step, pos_cache)

    per_stepper = stateful_per_step(skip)

    yield from bp.list_scan(dets, s_stage.px, list(loc177[0]), 
                                s_stage.py, list(loc177[1]), 
                                per_step=per_stepper, md=md)


@inject_md_decorator({'macro_name': 'loc_cust_scan'})
def loc_cust_scan(dets, cust_locs, skip=0, md={}):
    """loc_cust_scan scans across a library with 177 points, measuring each 
    detector in dets

    :param dets: detectors to be 
    :type dets: list
    :param cust_locs: (2, N) array denoting N locations to scan.  First list 
                      will direct px and the second will direct py 
    :type cust_locs: list
    :param skip: number of data points to skip
    :yield: things from list_scan
    :rtype: Msg
    """
    # format locations and stage motors
    if I0 not in dets:
        dets.append(I0)
    if I1 not in dets:
        dets.append(I1)

    if xsp3 in dets:
        yield from bps.mv(xsp3.total_points, len(cust_locs[0]))

    # inject logic via per_step 
    class stateful_per_step:
        
        def __init__(self, skip):
            self.skip = skip
            self.cnt = 0
            #print(self.skip, self.cnt)

        def __call__(self, detectors, step, pos_cache):
            """
            has signature of bps.one_and_step, but with added logic of skipping 
            a point if it is outside of provided radius
            """
            if self.cnt < self.skip: # if not enough skipped
                self.cnt += 1
                pass
            else:
                yield from bps.one_nd_step(detectors, step, pos_cache)

    per_stepper = stateful_per_step(skip)

    yield from bp.list_scan(dets, s_stage.px, list(cust_locs[0]), 
                                s_stage.py, list(cust_locs[1]), 
                                per_step=per_stepper, md=md)

# collection plans
# Basic dark > light collection plan
@inject_md_decorator({'macro_name':'dark_light_plan'})
def dark_light_plan(dets, shutter=fs, md={}):
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
    if I0 not in dets:
        dets.append(I0)
    if I1 not in dets:
        dets.append(I1)

    start_time = time.time()
    uids = []

    #close fast shutter, take a dark
    yield from bps.mv(fs, 1)
    mdd = md.copy()
    mdd.update(im_type='dark')
    uid = yield from bp.count(dets, md=mdd)
    uids.append(uid)


    # open fast shutter, take light
    yield from bps.mv(fs, 0)
    mdl = md.copy()
    mdl.update(im_type='primary')
    uid = yield from bp.count(dets, md=mdl)
    uids.append(uid)

    end_time = time.time()
    print(f'Duration: {end_time - start_time:.3f} sec')

    plot_dark_corrected(db[uids])

    return(uids)


# Plan for meshgrid + dark/light?...

# image time series
@inject_md_decorator({'macro_name':'exposure_time_series'})
def exp_time_plan(det, timeList=[1]):
    '''
    Run count with each exposure time in time list.  
    Specific to Dexela Detector, only run with single detector
    return uids from each count

    # TO-DO: Fix so both are under the same start document
    '''
    primary_det = det
    dets = []
    if I0 not in dets:
        dets.append(I0)
    if I1 not in dets:
        dets.append(I1)

    dets.append(primary_det)
    md = {'acquire_time': 0, 'plan_name': 'exp_time_plan'}
    uids = []
    for time in timeList:
        # set acquire time
        yield from bps.mov(primary_det.cam.acquire_time, time)
        md['acquire_time'] = time
        uid = yield from bp.count(dets, md=md)

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
        if hdr.start['im_type']=='dark':
            darkarr = hdr.table(fill=True)['dexela_image'][1]
        elif hdr.start['im_type'] == 'primary':
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

@inject_md_decorator({'macro_name':'multi_acquire_plan'})
def multi_acquire_plan(det, acq_time, reps): 
    '''multiple acquisition run.  Single dark image, multiple light
    '''
    yield from bps.mv(det.cam.acquire_time, acq_time) 
    print(det.cam.acquire_time.read()) 
    yield from bps.mv(fs, 1) 
    dark_uid = yield from bp.count([det], md={'name':'dark'}) 
    yield from bps.mv(fs, 0) 
    light_uids = [] 
    
    for _ in range(reps): 
        light_uid = yield from bp.count([det], md={'name':'primary'}) 
        light_uids.append(light_uid) 
    
    return (dark_uid, light_uids) 

@inject_md_decorator({'macro_name': 'level_s_stage'})    
def level_s_stage():
    """level_s_stage level s_stage vx, vy

    double wafer stage: (-85, 85), (-58, 85)
    """
    # level on y axis
    yield from bps.mv(s_stage.px, 0, s_stage.py, 0)
    yield from level_stage_single(lrf, s_stage.vx, s_stage.px, -50, 50)

    # level on x axis
    yield from bps.mv(s_stage.px, 0, s_stage.py, 0)
    yield from level_stage_single(lrf, s_stage.vy, s_stage.py, 60, -60)


@inject_md_decorator({'marco_name': 'tablev_scan'})
def tablev_scan():
    '''
    send signal to DO01 to trigger tablev_scan
    '''
    yield from bps.mv(table_trigger, 0) # start tablev_scan
    yield from bps.sleep(1)

    if I0.get() < 0.01: # If we don't have beam
        print('No beam, aborting...')
        yield from bps.mv(table_trigger, 1) # end tablev_scan
        return

    # sleep until we see the busy signal go high
    cnt = 0
    while (table_busy.read()[table_busy.name]['value'] < 0.5) and cnt < 100: 
        print('waiting for busy signal...') 
        yield from bps.sleep(2)
        cnt += 1 

    # Turn off trigger signal
    yield from bps.mv(table_trigger, 1)

def tuned_mesh_grid_scan(AD, mot1, s1, f1, int1, mot2, s2, f2, int2, 
            radius, ROI=1, pin=None, skip=0, md=None):
    '''
    Attempt to be intelligent about which points on a grid are scanned
    Tune within per_step plan based on signal from xsp3 roi.  
        - scan with xsp3
        - find peak location
        - move to peak location
        - collect AD
    AD must be some area detector 
    '''
    raise NotImplementedError

    # Add other relevant detectors
    if I0 not in dets:
        dets.append(I0)
    if I1 not in dets:
        dets.append(I1)

    # Determine points for meshgrid 
    # Verification (check non-negative, motors are motors, non-zero steps?)
    if (s1 >= f1) or (s2 >= f2):
        raise ValueError('starting bounds must be less than end bounds')
    # Basic plan logic
    ## Define new bounds
    if not pin: # no pinning tuple provided
        pin = (mot1.position, mot2.position) 

    if (pin[0] < s1) or (f1 < pin[0]) or (pin[1] < s2) or (f2 < pin[1]):
        raise ValueError('pin location not inside defined grid')

    ## subtract fraction of interval to account for edges
    s1_new = np.arange(pin[0], s1-int1/2, -int1)[-1]
    f1_new = np.arange(pin[0], f1+int1/2, int1)[-1]

    s2_new = np.arange(pin[1], s2-int2/2, -int2)[-1]
    f2_new = np.arange(pin[1], f2+int2/2, int2)[-1]

    ## add half of interval to include endpoints if interval is perfect
    num1 = len(np.arange(s1_new, f1_new+int1/2, int1))
    num2 = len(np.arange(s2_new, f2_new+int2/2, int2))
    
    center = (s1+(f1-s1)/2, s2+(f2-s2)/2)

    motor_args = list([mot1, s1_new, f1_new, num1, 
                        mot2, s2_new, f2_new, num2, False])

    # metadata addition
    _md = {'radius': radius}
    _md.update(md or {})

    # parameters for _refine_scan
    peak_stats = PeakStats(x=motor.name, y=signal.name)

    # start plans
    @subs_decorator(peak_stats)
    def _refine_scan(md=None):

        yield from bp.rel_scan([signal], motor, -width/2, width/2, num)

        # Grab final position from subscribed peak_stats
        valid_peak = peak_stats.max[-1] >= (4 * peak_stats.min[-1])
        if peak_stats.max is None:
            valid_peak = False

        final_position = 
        if valid_peak: # Condition for finding a peak
            if peak_choice == 'cen':
                final_position = peak_stats.cen
            elif peak_choice == 'com':
                final_position = peak_stats.com

        yield from bps.mv(motor, final_position)


    # inject logic via per_step 
    class stateful_per_step:
        
        def __init__(self, skip):
            self.skip = skip
            self.cnt = 0
            #print(self.skip, self.cnt)

        def __call__(self, detectors, step, pos_cache):
            """
            has signature of bps.one_and_step, but with added logic of skipping 
            a point if it is outside of provided radius
            """
            if self.cnt < self.skip: # if not enough skipped
                self.cnt += 1
                pass
            else:
                # rel_scan and refine
                yield from _refine_scan()
                # acquire
                yield from bps.one_nd_step(detectors, step, pos_cache)

    per_stepper = stateful_per_step(skip)

    # Skip points if need
    newGen = bp.grid_scan(detectors, *motor_args, 
                            per_step=per_stepper, md=_md)
    return (yield from newGen)