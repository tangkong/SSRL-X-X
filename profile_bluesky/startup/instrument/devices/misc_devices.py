"""
Miscellaneous devices
"""
__all__ = ['shutter', 'I1', 'I0', 'lrf', 'table_trigger', 'table_busy',
            'filter1', 'filter2', 'filter3', 'filter4']

from ophyd import EpicsSignalRO, EpicsSignal, Device, Component as Cpt

shutter = EpicsSignal('BL00:RIO.DO00', name='FastShutter')
I1 = EpicsSignalRO('BL00:RIO.AI2', name='I1')
I0 = EpicsSignalRO('BL00:RIO.AI1', name='I0')

lrf = EpicsSignalRO('BL00:RIO.AI0', name='lrf')

table_trigger = EpicsSignal('BL00:RIO.DO01', name='tablev_scan trigger')
table_busy = EpicsSignalRO('BL00:RIO.AI3', name='tablev_scan busy')

filter1 = EpicsSignal('BL00:RIO.AO1', name='filter1') # high (4.9V) = filter out
filter2 = EpicsSignal('BL00:RIO.AO2', name='filter2') 
filter3 = EpicsSignal('BL00:RIO.AO3', name='filter3') 
filter4 = EpicsSignal('BL00:RIO.AO4', name='filter4') 

class FilterBox(Device):
    filter1 = Cpt(EpicsSignal, 'BL00:RIO.AO1')
    filter2 = Cpt(EpicsSignal, 'BL00:RIO.AO2')
    filter3 = Cpt(EpicsSignal, 'BL00:RIO.AO3')
    filter4 = Cpt(EpicsSignal, 'BL00:RIO.AO4')

    _filter_list = [filter1, filter2, filter3, filter4]
    valid_open_values = ['open', 'opened']
    valid_close_values = ['close', 'closed']

    open_value = 0
    close_value = 1

    def __init__(self, prefix, *, config=[1,1,1,1], **kwargs):
        """ Register components and initialize with configuration 
        filter_box = FilterBox()
        """
        self.config = config
        self.thicks = [0.89, 2.52, 3.83, 10.87]

        # set filters
        for i in range(4):
            self.set_filter(i, 'close')

        super().__init__(prefix, **kwargs)
        

    def set_filter(self, num, state):
        """ set filter in or out"""

        if state in self.valid_open_values:
            self._filter_list[num].put(self.open_value)
        elif state in self.valid_close_values:
            self._filter_list[num].put(self.close_value)
        else: 
            raise ValueError('setting not a valid open or close state')
    
    def status(self):
        print('status:.....')

    def step_up(self):
        print('filters incremented')
    
    def step_down(self):
        print('filters decremented')

    def 